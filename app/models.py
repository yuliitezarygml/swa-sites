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
    release_date = db.Column(db.String(50))
    developer = db.Column(db.String(100))
    path = db.Column(db.String(200))
    dlc = db.Column(db.Text)
    # Добавляем поля для систем
    windows = db.Column(db.Boolean, default=False)
    mac = db.Column(db.Boolean, default=False)
    linux = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(500))
    description = db.Column(db.Text)
    
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

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)  # Поле для проверки админа

    def __init__(self, username, password_hash, is_admin=False):
        self.id = username  # Используем username как id
        self.username = username
        self.password_hash = password_hash
        self.is_admin = is_admin

    @staticmethod
    def get_user(username):
        users = User.load_users()
        user_data = users.get(username)
        if user_data:
            return User(
                username=username,
                password_hash=user_data['password_hash'],
                is_admin=user_data.get('is_admin', False)
            )
        return None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

    @staticmethod
    def create_user(username, password, is_admin=False):
        users = User.load_users()
        if username not in users:
            users[username] = {
                'password_hash': generate_password_hash(password),
                'is_admin': is_admin
            }
            User.save_users(users)
            return True
        return False

    @staticmethod
    def verify_user(username, password):
        user = User.get_user(username)
        if user and user.check_password(password):
            return user
        return None 

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

class Developer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100))
    discord = db.Column(db.String(100))
    avatar = db.Column(db.String(500))
    description = db.Column(db.Text) 