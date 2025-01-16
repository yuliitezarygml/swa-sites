from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from app.config import Config
import os
import json
from werkzeug.security import generate_password_hash
import logging
from logging.handlers import RotatingFileHandler
from datetime import timedelta

# Создаем экземпляр Flask
app = Flask(__name__)
app.config.from_object(Config)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Создаем экземпляр SQLAlchemy
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Импортируем маршруты после создания db
from app import routes, models
from app.models import User

@login_manager.user_loader
def load_user(user_id):
    return User.get_user(user_id)

# Создаем директорию instance если её нет
if not os.path.exists('instance'):
    os.makedirs('instance')

# Создаем или проверяем файл base.txt
base_file = 'instance/base.txt'
if not os.path.exists(base_file):
    initial_data = {
        "admin": {
            "password_hash": generate_password_hash("admin123"),  # Используем более надежный пароль
            "is_admin": True
        }
    }
    with open(base_file, 'w') as f:
        json.dump(initial_data, f, indent=4)

# Создаем все таблицы
with app.app_context():
    db.create_all() 

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/swa_game_service.log', maxBytes=10240, backupCount=10)
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s [in %(pathname)s:%(lineno)d]'
    )
    file_handler.setFormatter(formatter)
    app.logger.setLevel(logging.INFO)
    app.logger.info('SWA Game Service startup') 

if not app.debug:
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'
    ))
    app.logger.addHandler(file_handler) 