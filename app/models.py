from datetime import datetime, timedelta
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import json
import os

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    game_id = db.Column(db.String(20), unique=True, nullable=False)
    developer = db.Column(db.String(100))
    release_date = db.Column(db.String(50))
    path = db.Column(db.String(200))  # для URL изображения
    dlc = db.Column(db.Text)
    windows = db.Column(db.Boolean, default=False)
    mac = db.Column(db.Boolean, default=False)
    linux = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(500))
    access_type = db.Column(db.String(20), default='paid')  # free, paid, subscription
    drm_notice = db.Column(db.Text)
    
    __table_args__ = (
        db.Index('idx_game_id', 'game_id'),
        db.Index('idx_name', 'name'),
    )
    
class LauncherGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    path = db.Column(db.String(200), nullable=False)
    startfile = db.Column(db.String(200), nullable=False)
    dwlnk = db.Column(db.String(200), nullable=False)
    source = db.Column(db.String(500)) 

class ActiveUsers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), unique=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    @classmethod
    def clean_inactive(cls):
        # Удаляем сессии старше 10 минут
        ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10)
        cls.query.filter(cls.last_seen < ten_minutes_ago).delete()
        db.session.commit()
    
    @classmethod
    def get_active_count(cls):
        cls.clean_inactive()
        return cls.query.count() 

class User(UserMixin):
    def __init__(self, username):
        self.username = username
        self._is_admin = False  # Приватное свойство для хранения статуса админа
        
        # Проверяем права администратора при создании
        users = self.load_users()
        user_data = users.get(username)
        if user_data:
            self._is_admin = user_data.get('is_admin', False)

    def get_id(self):
        return self.username

    @staticmethod
    def get_user(user_id):
        users = User.load_users()
        if user_id in users:
            user = User(user_id)
            return user
        return None

    @staticmethod
    def load_users():
        if not os.path.exists('instance/base.txt'):
            return {}
        try:
            with open('instance/base.txt', 'r') as f:
                return json.load(f)
        except:
            return {}

    @staticmethod
    def save_users(users):
        os.makedirs('instance', exist_ok=True)
        with open('instance/base.txt', 'w') as f:
            json.dump(users, f, indent=4)

    @property
    def is_admin(self):
        return self._is_admin

    @is_admin.setter
    def is_admin(self, value):
        self._is_admin = value

class Statistics:
    @staticmethod
    def load_stats():
        try:
            with open('instance/statistics.txt', 'r') as f:
                return json.load(f)
        except:
            return {"total_visits": 0}

    @staticmethod
    def save_stats(stats):
        os.makedirs('instance', exist_ok=True)
        with open('instance/statistics.txt', 'w') as f:
            json.dump(stats, f, indent=4)

    @staticmethod
    def increment_visits():
        stats = Statistics.load_stats()
        stats["total_visits"] = stats.get("total_visits", 0) + 1
        Statistics.save_stats(stats)
        return stats["total_visits"]

    @staticmethod
    def get_total_visits():
        stats = Statistics.load_stats()
        return stats.get("total_visits", 0) 