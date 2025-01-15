from flask import jsonify, send_file, abort, request, render_template, redirect, url_for, flash, session
from app import app, db
from app.models import Game, LauncherGame, ActiveUsers, User, Statistics, Developer
import os
import json
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename
import uuid
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from pathlib import Path

# Добавляем фильтр dirname
@app.template_filter('dirname')
def dirname_filter(path):
    return os.path.dirname(path)

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Админ-панель для управления играми
@app.route('/admin/games', methods=['GET'])
@admin_required
def admin_games():
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Количество игр на странице
    
    # Получаем игры с пагинацией
    games = Game.query.paginate(page=page, per_page=per_page, error_out=False)
    launcher_games = LauncherGame.query.all()
    
    return render_template('admin/games.html', 
                         games=games,
                         launcher_games=launcher_games,
                         json=json)

# Добавление новой игры
@app.route('/admin/games/add', methods=['GET', 'POST'])
@admin_required
def add_game():
    if request.method == 'POST':
        game_id = request.form['game_id']
        name = request.form['name']
        dlc = request.form.getlist('dlc[]')
        
        # Проверяем, существует ли игра с таким game_id
        existing_game = Game.query.filter_by(game_id=game_id).first()
        if existing_game:
            flash(f'Game with ID {game_id} already exists!', 'error')
            return redirect(url_for('add_game'))
        
        try:
            # Сохраняем файл игры, если он был загружен
            game_file = request.files.get('game_file')
            file_path = None
            if game_file and game_file.filename:
                filename = f"{game_id}.zip"
                file_path = os.path.join(app.config['GAMEID_FOLDER'], filename)
                os.makedirs(app.config['GAMEID_FOLDER'], exist_ok=True)
                game_file.save(file_path)
            
            # Создаем новую запись в базе данных
            game = Game(
                game_id=game_id,
                name=name,
                dlc=json.dumps(dlc) if dlc else None,
                file_path=file_path
            )
            
            db.session.add(game)
            db.session.commit()
            flash('Game added successfully!', 'success')
            return redirect(url_for('admin_games'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding game: {str(e)}', 'error')
            return redirect(url_for('add_game'))
            
    return render_template('admin/add_game.html')

# API эндпоинты
@app.route('/api/fetch_gameid/<game_id>')
def fetch_game_id(game_id):
    game = Game.query.filter_by(game_id=game_id).first()
    if game:
        return jsonify({
            "id": game.game_id,
            "name": game.name,
            "dlc": json.loads(game.dlc),
            "path": game.path
        })
    abort(404)

@app.route('/static/launcher.json')
def get_launcher():
    games = LauncherGame.query.all()
    launcher_data = {}
    for game in games:
        launcher_data[game.name] = {
            "path": game.path,
            "startfile": game.startfile,
            "dwlnk": game.dwlnk,
            "source": game.source
        }
    return jsonify(launcher_data)

@app.route('/api/stats')
def get_stats():
    stats = {
        "daily_users": 275,
        "online_users": 6,
        "total_users": 1434,
        "last_reset": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "next_reset": {
            "next_reset_at": (datetime.now()).strftime("%Y-%m-%d %H:%M:%S"),
            "next_reset_in_seconds": 23902
        }
    }
    return jsonify(stats)

@app.route('/api/download/<path:filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join(app.config['DOWNLOADS_FOLDER'], filename),
            as_attachment=True
        )
    except:
        abort(404)

@app.route('/api/download/luapacka.exe')
def download_luapacka():
    try:
        return send_file(
            os.path.join(app.config['DOWNLOADS_FOLDER'], 'luapacka.exe'),
            as_attachment=True
        )
    except:
        abort(404)

@app.route('/api/gameid/<game_id>.zip')
def get_game_files(game_id):
    try:
        return send_file(
            os.path.join(app.config['GAMEID_FOLDER'], f'{game_id}.zip'),
            as_attachment=True
        )
    except:
        abort(404)

@app.route('/gamelist')
def gamelist():
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Количество игр на странице
    
    # Получаем все игры с пагинацией
    games = Game.query.paginate(page=page, per_page=per_page, error_out=False)
    
    total_games = Game.query.count()
    
    return render_template('gamelist.html', 
                         games=games,
                         total_games=total_games,
                         current_page=page,
                         json=json)

@app.before_request
def before_request():
    # Не считаем статические файлы и повторные запросы от того же пользователя в течение сессии
    if not request.path.startswith('/static/') and 'visited' not in session:
        Statistics.increment_visits()
        session['visited'] = True
    
    if not session.get('user_id'):
        session['user_id'] = str(uuid.uuid4())
        session.permanent = True
    
    # Обновляем или создаем запись об активном пользователе
    active_user = ActiveUsers.query.filter_by(session_id=session['user_id']).first()
    if active_user:
        active_user.last_seen = datetime.utcnow()
    else:
        active_user = ActiveUsers(session_id=session['user_id'])
        db.session.add(active_user)
    db.session.commit()

@app.route('/')
def home():
    stats = {
        'total_games': Game.query.count(),
        'online_users': ActiveUsers.get_active_count(),
        'total_users': Statistics.get_total_visits()  # Используем общее количество посещений
    }
    return render_template('home.html', stats=stats)

@app.route('/swa')
def swa():
    # Страница SWA
    return "SWA Page"

# Обновляем маршрут для управления файлами
@app.route('/admin/files')
@admin_required
def file_browser():
    # Получаем путь из параметров или используем корневую папку проекта
    current_path = request.args.get('path', '')
    base_path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    
    if current_path:
        full_path = os.path.join(base_path, current_path)
    else:
        full_path = base_path
        
    # Проверяем, что путь не выходит за пределы корневой папки
    if not os.path.commonpath([base_path]) == os.path.commonpath([base_path, full_path]):
        flash('Access denied', 'error')
        return redirect(url_for('file_browser'))
    
    try:
        # Получаем список файлов и папок
        items = []
        for item in os.scandir(full_path):
            size = os.path.getsize(item.path) if item.is_file() else 0
            modified = os.path.getmtime(item.path)
            items.append({
                'name': item.name,
                'is_dir': item.is_dir(),
                'size': size,
                'modified': datetime.fromtimestamp(modified),
                'path': os.path.join(current_path, item.name) if current_path else item.name
            })
        
        # Сортируем: сначала папки, потом файлы
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        
        return render_template('admin/file_browser.html', 
                             items=items, 
                             current_path=current_path,
                             parent_path=os.path.dirname(current_path) if current_path else None)
    except PermissionError:
        flash('Permission denied', 'error')
        return redirect(url_for('file_browser'))
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('file_browser'))

# Маршрут для удаления игры
@app.route('/admin/games/delete/<int:id>')
@admin_required
def delete_game(id):
    game = Game.query.get_or_404(id)
    try:
        db.session.delete(game)
        db.session.commit()
        flash('Game deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting game: {str(e)}', 'error')
    return redirect(url_for('admin_games'))

# Маршрут для удаления файла
@app.route('/admin/files/delete/<path:filename>')
@admin_required
def delete_file(filename):
    try:
        file_path = os.path.join(app.config['GAMEID_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash(f'File {filename} was successfully deleted.', 'success')
        else:
            flash(f'File {filename} not found.', 'error')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')
    return redirect(url_for('manage_files'))

# Добавим обработку 404 ошибки
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404 

@app.route('/admin/games/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_game(id):
    game = Game.query.get_or_404(id)
    if request.method == 'POST':
        game.game_id = request.form['game_id']
        game.name = request.form['name']
        game.dlc = json.dumps(request.form.getlist('dlc[]'))
        try:
            db.session.commit()
            flash('Game updated successfully!', 'success')
            return redirect(url_for('admin_games'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating game: {str(e)}', 'error')
    
    return render_template('admin/edit_game.html', game=game, json=json)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.verify_user(username, password)
        
        if user:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home')) 

@app.route('/register', methods=['GET', 'POST'])
@admin_required  # Только админ может создавать новых пользователей
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        
        if User.create_user(username, password, is_admin):
            flash('User created successfully!', 'success')
            return redirect(url_for('admin_games'))
        else:
            flash('Username already exists', 'error')
    
    return render_template('register.html') 

# Добавьте в начало файла конфигурацию для загрузки изображений
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = 'app/static/game_images'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/game/edit/<int:game_id>', methods=['GET', 'POST'])
@admin_required
def edit_game_details(game_id):
    game = Game.query.get_or_404(game_id)
    
    if request.method == 'POST':
        game.name = request.form['name']
        game.game_id = request.form['game_id']
        game.release_date = request.form['release_date'] or None
        game.developer = request.form['developer']
        
        # Обработка загрузки изображения
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{game.game_id}_{file.filename}")
                if not os.path.exists(UPLOAD_FOLDER):
                    os.makedirs(UPLOAD_FOLDER)
                file_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(file_path)
                game.path = f"/static/game_images/{filename}"

        # Обработка DLC
        dlc_list = request.form.getlist('dlc[]')
        if dlc_list:
            game.dlc = json.dumps(dlc_list)
        else:
            game.dlc = None

        # Обработка систем
        game.windows = 'windows' in request.form
        game.mac = 'mac' in request.form
        game.linux = 'linux' in request.form

        db.session.commit()
        flash('Game updated successfully!', 'success')
        return redirect(url_for('gamelist'))
    
    # Добавляем json в контекст шаблона
    return render_template('edit_game.html', game=game, json=json) 

@app.route('/admin/files/delete/<path:filepath>', methods=['POST'])
@admin_required
def delete_file_path(filepath):
    try:
        # Используем текущую директорию вместо uploads
        full_path = os.path.join(os.getcwd(), filepath)
        if os.path.exists(full_path) and os.path.isfile(full_path):
            os.remove(full_path)
            flash('File deleted successfully', 'success')
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}', 'error')
    return redirect(url_for('file_browser'))

@app.route('/admin/files/rename', methods=['POST'])
@admin_required
def rename_file():
    old_name = request.form.get('old_name')
    new_name = request.form.get('new_name')
    current_path = request.form.get('current_path', '')
    
    try:
        old_path = os.path.join(app.config['UPLOAD_FOLDER'], current_path, old_name)
        new_path = os.path.join(app.config['UPLOAD_FOLDER'], current_path, new_name)
        
        if os.path.exists(old_path):
            os.rename(old_path, new_path)
            flash('File renamed successfully', 'success')
        else:
            flash('File not found', 'error')
    except Exception as e:
        flash(f'Error renaming file: {str(e)}', 'error')
    
    return redirect(url_for('file_browser', path=current_path)) 

@app.route('/admin/files/edit/<path:filepath>', methods=['GET', 'POST'])
@admin_required
def edit_file_content(filepath):
    # Используем текущую директорию вместо uploads
    full_path = os.path.join(os.getcwd(), filepath)
    
    if request.method == 'POST':
        try:
            content = request.form.get('content')
            with open(full_path, 'w', encoding='utf-8') as file:
                file.write(content)
            flash('File content updated successfully', 'success')
            return redirect(url_for('file_browser', path=os.path.dirname(filepath)))
        except Exception as e:
            flash(f'Error updating file: {str(e)}', 'error')
            
    try:
        with open(full_path, 'r', encoding='utf-8') as file:
            content = file.read()
        return render_template('admin/edit_file.html', 
                             filepath=filepath, 
                             content=content,
                             filename=os.path.basename(filepath))
    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'error')
        return redirect(url_for('file_browser')) 

@app.route('/developers')
def developers():
    # Получаем разработчиков из базы данных вместо хардкода
    developers = Developer.query.all()
    return render_template('developers.html', developers=developers)

@app.route('/admin/developers', methods=['GET'])
@admin_required
def admin_developers():
    developers = Developer.query.all()
    return render_template('admin/developers.html', developers=developers)

# Обновляем константы
UPLOAD_FOLDER = os.path.join('app', 'static', 'avatars')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папку для аватаров, если её нет
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/developers/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_developer(id):
    developer = Developer.query.get_or_404(id)
    
    if request.method == 'POST':
        developer.name = request.form['name']
        developer.role = request.form['role']
        developer.discord = request.form['discord']
        developer.description = request.form['description']
        
        # Обработка загрузки нового аватара
        avatar_file = request.files.get('avatar')
        if avatar_file and avatar_file.filename:
            if allowed_file(avatar_file.filename):
                # Удаляем старый аватар если он существует
                if developer.avatar:
                    old_avatar_path = os.path.join(app.root_path, 'static', 'avatars', os.path.basename(developer.avatar))
                    if os.path.exists(old_avatar_path):
                        os.remove(old_avatar_path)
                
                # Сохраняем новый аватар
                filename = secure_filename(f"{uuid.uuid4()}{os.path.splitext(avatar_file.filename)[1]}")
                avatar_path = os.path.join(UPLOAD_FOLDER, filename)
                avatar_file.save(avatar_path)
                developer.avatar = f"/static/avatars/{filename}"
                
                print(f"Saved avatar to: {avatar_path}")  # Для отладки
            else:
                flash('Invalid file type. Allowed types are: png, jpg, jpeg, gif, webp', 'error')
                return redirect(url_for('edit_developer', id=id))
        
        db.session.commit()
        flash('Developer updated successfully!', 'success')
        return redirect(url_for('developers'))
    
    return render_template('admin/edit_developer.html', developer=developer)

@app.route('/admin/developers/add', methods=['GET', 'POST'])
@admin_required
def add_developer():
    if request.method == 'POST':
        avatar_file = request.files.get('avatar')
        avatar_path = None
        
        if avatar_file and avatar_file.filename:
            if allowed_file(avatar_file.filename):
                filename = secure_filename(f"{uuid.uuid4()}{os.path.splitext(avatar_file.filename)[1]}")
                avatar_file.save(os.path.join(UPLOAD_FOLDER, filename))
                avatar_path = f"/static/avatars/{filename}"
            else:
                flash('Invalid file type. Allowed types are: png, jpg, jpeg, gif, webp', 'error')
                return redirect(url_for('add_developer'))
        
        developer = Developer(
            name=request.form['name'],
            role=request.form['role'],
            discord=request.form['discord'],
            description=request.form['description'],
            avatar=avatar_path
        )
        
        db.session.add(developer)
        db.session.commit()
        flash('Developer added successfully!', 'success')
        return redirect(url_for('developers'))
        
    return render_template('admin/edit_developer.html', developer=None)

@app.route('/admin/developers/delete/<int:id>', methods=['POST'])
@admin_required
def delete_developer(id):
    developer = Developer.query.get_or_404(id)
    
    # Удаляем аватар
    if developer.avatar:
        avatar_path = os.path.join(app.root_path, developer.avatar.lstrip('/'))
        if os.path.exists(avatar_path):
            os.remove(avatar_path)
    
    db.session.delete(developer)
    db.session.commit()
    flash('Developer deleted successfully!', 'success')
    return redirect(url_for('admin_developers')) 