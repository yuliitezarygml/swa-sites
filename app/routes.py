from flask import jsonify, send_file, abort, request, render_template, redirect, url_for, flash, session, send_from_directory
from app import app, db
from app.models import Game, LauncherGame, ActiveUsers, User, Statistics, Developer, FileComment
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

# Удалим старые маршруты file_browser и добавим новые в админ секцию

@app.route('/file_browser/', defaults={'path': ''})
@app.route('/file_browser/<path:path>')
@login_required
@admin_required
def admin_files(path):
    # Изменим базовую директорию на корень проекта
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    abs_path = os.path.join(base_dir, path)
    
    # Проверка, что путь находится внутри разрешенной директории
    if not abs_path.startswith(base_dir):
        abort(403)
    
    if not os.path.exists(abs_path):
        abort(404)
    
    items = []
    if os.path.isdir(abs_path):
        for item in os.listdir(abs_path):
            # Пропускаем скрытые файлы и папки
            if item.startswith('.'):
                continue
                
            item_path = os.path.join(abs_path, item)
            is_dir = os.path.isdir(item_path)
            stat = os.stat(item_path)
            
            # Форматируем размер файла
            size = stat.st_size
            if not is_dir:
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size/1024:.1f} KB"
                else:
                    size_str = f"{size/(1024*1024):.1f} MB"
            else:
                size_str = ""
            
            # Получаем последний комментарий для файла
            comment = FileComment.query.filter_by(
                file_path=os.path.join(path, item).replace('\\', '/')
            ).order_by(FileComment.created_at.desc()).first()
            
            items.append({
                'name': item,
                'path': os.path.join(path, item).replace('\\', '/'),
                'is_dir': is_dir,
                'size': size_str,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                'comment': comment.comment if comment else None,
                'comment_date': comment.created_at.strftime('%Y-%m-%d %H:%M:%S') if comment else None
            })
        
        # Сортируем: сначала папки, потом файлы
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    path_parts = [p for p in path.split('/') if p]
    
    return render_template('admin/files.html',
                         items=items,
                         current_path=path,
                         path_parts=path_parts)

@app.route('/admin/files/edit/<path:path>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_file(path):
    # Используем корень проекта как базовую директорию
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    file_path = os.path.join(base_dir, path.lstrip('/'))
    
    # Проверка безопасности пути
    if not os.path.abspath(file_path).startswith(base_dir):
        abort(403)
    
    if not os.path.isfile(file_path):
        abort(404)
    
    if request.method == 'POST':
        content = request.form.get('content')
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            flash('File saved successfully!', 'success')
            return redirect(url_for('admin_files', path=os.path.dirname(path)))
        except Exception as e:
            flash(f'Error saving file: {str(e)}', 'error')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        flash('This file cannot be edited (binary file)', 'error')
        return redirect(url_for('admin_files', path=os.path.dirname(path)))
    except Exception as e:
        flash(f'Error reading file: {str(e)}', 'error')
        return redirect(url_for('admin_files', path=os.path.dirname(path)))
    
    return render_template('admin/edit_file.html', 
                         path=path,
                         content=content,
                         filename=os.path.basename(path))

@app.route('/admin/files/download/<path:path>')
@login_required
@admin_required
def admin_download_file(path):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    directory = os.path.join(base_dir, os.path.dirname(path))
    filename = os.path.basename(path)
    
    if not os.path.join(directory, filename).startswith(base_dir):
        abort(403)
    
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/admin/files/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_file():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        path = data.get('path')
        is_dir = data.get('is_dir', False)
        
        if not path:
            return jsonify({'error': 'No path provided'}), 400
        
        # Используем корень проекта как базовую директорию
        base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        full_path = os.path.join(base_dir, path.lstrip('/'))
        
        # Проверка безопасности пути
        if not os.path.abspath(full_path).startswith(base_dir):
            return jsonify({'error': 'Access denied'}), 403
            
        if not os.path.exists(full_path):
            return jsonify({'error': 'File or directory not found'}), 404
        
        try:
            if is_dir:
                import shutil
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
            return jsonify({'success': True, 'message': 'Successfully deleted'}), 200
            
        except PermissionError:
            return jsonify({'error': 'Permission denied'}), 403
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/admin/files/upload', methods=['POST'])
@login_required
@admin_required
def admin_upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Получаем текущий путь из формы
    current_path = request.form.get('current_path', '')
    
    # Используем корень проекта как базовую директорию
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    upload_path = os.path.join(base_dir, current_path.lstrip('/'))
    
    # Проверяем и создаем директорию, если её нет
    if not os.path.exists(upload_path):
        try:
            os.makedirs(upload_path)
        except Exception as e:
            return jsonify({'error': f'Could not create directory: {str(e)}'}), 500
    
    # Безопасное имя файла
    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_path, filename)
    
    # Если файл с таким именем существует, добавляем timestamp
    if os.path.exists(file_path):
        name, ext = os.path.splitext(filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(upload_path, filename)
    
    try:
        # Сохраняем файл
        file.save(file_path)
        
        # Получаем информацию о файле
        stat = os.stat(file_path)
        size = stat.st_size
        
        # Форматируем размер файла
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024 * 1024:
            size_str = f"{size/1024:.1f} KB"
        else:
            size_str = f"{size/(1024*1024):.1f} MB"
        
        return jsonify({
            'success': True,
            'name': filename,
            'path': os.path.join(current_path, filename).replace('\\', '/'),
            'size': size_str,
            'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Error saving file: {str(e)}'}), 500

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

# Добавляем константы для изображений игр
GAME_IMAGES_FOLDER = os.path.join('app', 'static', 'game_images')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Создаем папку для изображений игр, если её нет
if not os.path.exists(GAME_IMAGES_FOLDER):
    os.makedirs(GAME_IMAGES_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/admin/games/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_game(id):
    game = Game.query.get_or_404(id)
    
    if request.method == 'POST':
        game.name = request.form['name']
        game.game_id = request.form['game_id']
        game.release_date = request.form['release_date']
        game.developer = request.form['developer']
        game.windows = 'windows' in request.form
        game.mac = 'mac' in request.form
        game.linux = 'linux' in request.form
        
        # Обработка загрузки изображения
        if 'game_image' in request.files:
            file = request.files['game_image']
            if file and file.filename and allowed_file(file.filename):
                # Удаляем старое изображение если оно существует
                if game.image_path:
                    old_image_path = os.path.join(app.root_path, 'static', game.image_path.lstrip('/'))
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # Сохраняем новое изображение
                filename = secure_filename(f"game_{game.id}_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}")
                file_path = os.path.join(GAME_IMAGES_FOLDER, filename)
                file.save(file_path)
                game.image_path = f"/static/game_images/{filename}"
        
        db.session.commit()
        flash('Game updated successfully!', 'success')
        return redirect(url_for('gamelist'))
    
    return render_template('admin/edit_game.html', game=game)

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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home')) 

UPLOAD_FOLDER = os.path.join('app', 'static', 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', '7z', 'exe', 'msi'}

# Создаем папку для загрузок если её нет
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
@login_required
@admin_required
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # Получаем текущий путь из параметра
        current_path = request.form.get('current_path', '')
        upload_path = os.path.join(UPLOAD_FOLDER, current_path.lstrip('/'))
        
        # Создаем директорию если её нет
        if not os.path.exists(upload_path):
            os.makedirs(upload_path)
        
        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_path, filename)
        
        # Если файл существует, добавляем timestamp к имени
        if os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{name}_{timestamp}{ext}"
            file_path = os.path.join(upload_path, filename)
        
        file.save(file_path)
        
        # Получаем информацию о файле
        file_stat = os.stat(file_path)
        file_info = {
            'name': filename,
            'path': os.path.join(current_path, filename),
            'size': file_stat.st_size,
            'modified': datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return jsonify(file_info), 200
    
    return jsonify({'error': 'File type not allowed'}), 400 

@app.route('/admin/games/edit/<int:game_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_game_details(game_id):
    game = Game.query.get_or_404(game_id)
    
    if request.method == 'POST':
        game.name = request.form['name']
        game.game_id = request.form['game_id']
        game.release_date = request.form['release_date']
        game.developer = request.form['developer']
        game.windows = 'windows' in request.form
        game.mac = 'mac' in request.form
        game.linux = 'linux' in request.form
        
        # Обработка загрузки изображения
        if 'game_image' in request.files:
            file = request.files['game_image']
            if file and file.filename and allowed_file(file.filename):
                # Удаляем старое изображение если оно существует
                if game.image_path:
                    old_image_path = os.path.join(app.root_path, 'static', game.image_path.lstrip('/'))
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                # Сохраняем новое изображение
                filename = secure_filename(f"game_{game.id}_{uuid.uuid4()}{os.path.splitext(file.filename)[1]}")
                file_path = os.path.join(GAME_IMAGES_FOLDER, filename)
                file.save(file_path)
                game.image_path = f"/static/game_images/{filename}"
        
        db.session.commit()
        flash('Game updated successfully!', 'success')
        return redirect(url_for('admin_games'))
    
    return render_template('admin/edit_game.html', game=game) 

@app.route('/file_browser/', defaults={'path': ''})
@app.route('/file_browser/<path:path>')
@login_required
@admin_required
def file_browser(path):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    abs_path = os.path.join(base_dir, path)
    
    # Проверка, что путь находится внутри разрешенной директории
    if not abs_path.startswith(base_dir):
        abort(403)
    
    if not os.path.exists(abs_path):
        abort(404)
    
    items = []
    if os.path.isdir(abs_path):
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            is_dir = os.path.isdir(item_path)
            stat = os.stat(item_path)
            
            items.append({
                'name': item,
                'path': os.path.join(path, item).replace('\\', '/'),
                'is_dir': is_dir,
                'size': stat.st_size if not is_dir else None,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Сортируем: сначала папки, потом файлы
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
    
    path_parts = [p for p in path.split('/') if p]
    
    return render_template('file_browser.html',
                         items=items,
                         current_path=path,
                         path_parts=path_parts)

@app.route('/edit/<path:path>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_file(path):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.join(base_dir, path)
    
    # Проверка безопасности пути
    if not file_path.startswith(base_dir):
        abort(403)
    
    if not os.path.isfile(file_path):
        abort(404)
    
    if request.method == 'POST':
        content = request.form.get('content')
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            flash('File saved successfully!', 'success')
            return redirect(url_for('file_browser', path=os.path.dirname(path)))
        except Exception as e:
            flash(f'Error saving file: {str(e)}', 'error')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        flash('This file cannot be edited (binary file)', 'error')
        return redirect(url_for('file_browser', path=os.path.dirname(path)))
    
    return render_template('edit_file.html', 
                         path=path,
                         content=content,
                         filename=os.path.basename(path))

@app.route('/delete', methods=['POST'])
@login_required
@admin_required
def delete_item():
    data = request.get_json()
    path = data.get('path')
    is_dir = data.get('is_dir', False)
    
    base_dir = os.path.abspath(os.path.dirname(__file__))
    full_path = os.path.join(base_dir, path)
    
    # Проверка безопасности пути
    if not full_path.startswith(base_dir):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        if is_dir:
            import shutil
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 

@app.route('/admin/files/comment', methods=['POST'])
@login_required
@admin_required
def add_file_comment():
    data = request.get_json()
    path = data.get('path')
    comment = data.get('comment')
    
    if not path or not comment:
        return jsonify({'error': 'Path and comment are required'}), 400
        
    file_comment = FileComment(
        file_path=path,
        comment=comment,
        user_id=current_user.id
    )
    
    db.session.add(file_comment)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'comment': comment,
        'created_at': file_comment.created_at.strftime('%Y-%m-%d %H:%M:%S')
    }) 