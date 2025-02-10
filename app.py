import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'замените-на-надежный-ключ'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///darktube.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'mkv'}

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Модели
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    videos = db.relationship('Video', backref='uploader', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(200), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Главная страница с поиском
@app.route('/')
def index():
    search_query = request.args.get('q')
    if search_query:
        videos = Video.query.filter(Video.title.contains(search_query)).order_by(Video.upload_date.desc()).all()
    else:
        videos = Video.query.order_by(Video.upload_date.desc()).all()
    return render_template('index.html', videos=videos, query=search_query)

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('register'))
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Регистрация успешна. Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# Вход в систему
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password, password):
            flash('Неправильное имя пользователя или пароль', 'danger')
            return redirect(url_for('login'))
        login_user(user)
        flash('Вы успешно вошли в систему', 'success')
        return redirect(url_for('index'))
    return render_template('login.html')

# Выход из системы
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# Загрузка видео (только для авторизованных пользователей)
@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        if 'video' not in request.files:
            flash('Файл не найден', 'danger')
            return redirect(request.url)
        file = request.files['video']
        if file.filename == '':
            flash('Не выбран файл', 'danger')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Создание папки uploads, если её нет
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            new_video = Video(title=title, description=description, filename=filename, user_id=current_user.id)
            db.session.add(new_video)
            db.session.commit()
            flash('Видео загружено успешно', 'success')
            return redirect(url_for('index'))
        else:
            flash('Неподдерживаемый формат файла', 'danger')
            return redirect(request.url)
    return render_template('upload.html')

# Просмотр видео
@app.route('/video/<int:video_id>')
def video(video_id):
    video = Video.query.get_or_404(video_id)
    # Выбираем 5 последних видео, кроме текущего, для рекомендаций
    recommended_videos = Video.query.filter(Video.id != video_id).order_by(Video.upload_date.desc()).limit(5).all()
    return render_template('video.html', video=video, recommended_videos=recommended_videos)


# Отдача загруженных файлов
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Создание таблиц, если их ещё нет
    app.run(debug=True)
