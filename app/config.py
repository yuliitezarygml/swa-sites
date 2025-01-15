import os
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta

class Config:
    SECRET_KEY = 'your-secret-key-here'
    DOWNLOADS_FOLDER = 'downloads'
    FETCH_GAMEID_FOLDER = 'fetch_gameid'
    GAMEID_FOLDER = 'gameid'
    STATIC_FOLDER = 'static'
    APP_VERSION = 'R.1.0 GFK'
    
    # Используем корневую директорию проекта
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    # Конфигурация базы данных
    SQLALCHEMY_DATABASE_URI = 'sqlite:///games.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Конфигурация загрузки файлов
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB max-limit
    UPLOAD_FOLDER = 'uploads' 
    
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=10)  # Время жизни сессии 