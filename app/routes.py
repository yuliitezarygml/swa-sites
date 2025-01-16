from flask import jsonify, send_file, abort, request, render_template, redirect, url_for, flash, session
from app import app, db
from app.models import Game, LauncherGame, ActiveUsers, User, Statistics
import os
import json
from datetime import datetime
import shutil
from werkzeug.utils import secure_filename
import uuid
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from pathlib import Path
from flask_caching import Cache
from urllib.parse import urlparse
from sqlalchemy import or_
from werkzeug.security import check_password_hash

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Добавляем фильтр dirname
@app.template_filter('dirname')
def dirname_filter(path):
    return os.path.dirname(path)

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('У вас нет прав для доступа к этой странице.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Админ-панель для управления играми
@app.route('/admin/games')
@admin_required
def admin_games():
    # Получаем параметр поиска
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    # Формируем запрос с поиском по имени и ID
    query = Game.query
    if search:
        query = query.filter(
            or_(
                Game.name.ilike(f'%{search}%'),  # Поиск по имени
                Game.game_id.ilike(f'%{search}%')  # Поиск по ID
            )
        )
    
    # Получаем игры с пагинацией
    games = query.order_by(Game.name).paginate(
        page=page,
        per_page=50,
        error_out=False
    )
    
    return render_template('admin/games.html', games=games, search=search)

# Добавление новой игры
@app.route('/admin/games/add', methods=['GET', 'POST'])
@admin_required
def add_game():
    if request.method == 'POST':
        game_id = request.form['game_id']
        name = request.form['name']
        developer = request.form['developer']
        release_date = request.form['release_date']
        access = request.form['access']
        drm_notice = request.form['drm_notice']
        dlc = request.form.get('dlc', '').split('\n')
        dlc = [d.strip() for d in dlc if d.strip()]

        # Обработка изображения
        image_path = None
        image_type = request.form.get('image_type')
        
        if image_type == 'url':
            image_path = request.form.get('image_url')
        elif image_type == 'file':
            image_file = request.files.get('image_file')
            if image_file and image_file.filename:
                # Создаем папку для изображений, если её нет
                images_folder = os.path.join(app.static_folder, 'game_images')
                os.makedirs(images_folder, exist_ok=True)
                
                # Генерируем безопасное имя файла
                filename = secure_filename(f"{game_id}_{image_file.filename}")
                file_path = os.path.join(images_folder, filename)
                
                # Сохраняем файл
                image_file.save(file_path)
                
                # Формируем путь для доступа через URL
                image_path = url_for('static', filename=f'game_images/{filename}')

        # Обработка платформ
        platforms = []
        if 'windows' in request.form: platforms.append('windows')
        if 'mac' in request.form: platforms.append('mac')
        if 'linux' in request.form: platforms.append('linux')
        
        try:
            # Сохраняем файл игры, если он был загружен
            game_file = request.files.get('game_file')
            file_path = None
            if game_file and game_file.filename:
                filename = secure_filename(f"{game_id}.zip")
                file_path = os.path.join(app.config['GAMEID_FOLDER'], filename)
                os.makedirs(app.config['GAMEID_FOLDER'], exist_ok=True)
                game_file.save(file_path)
            
            # Создаем новую запись в базе данных
            game = Game(
                game_id=game_id,
                name=name,
                developer=developer,
                release_date=release_date,
                path=image_path,
                dlc=json.dumps(dlc) if dlc else None,
                windows='windows' in platforms,
                mac='mac' in platforms,
                linux='linux' in platforms,
                file_path=file_path,
                access_type=access,
                drm_notice=drm_notice
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
@cache.cached(timeout=60)  # Кэшируем на 60 секунд
def get_stats():
    stats = {
        "daily_users": ActiveUsers.get_active_count(),
        "total_users": Statistics.get_total_visits(),
        "last_reset": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
@app.route('/gamelist/<int:page>')
def gamelist(page=1):
    # Получаем параметр поиска из URL
    search_query = request.args.get('search', '').strip()
    
    # Формируем базовый запрос
    query = Game.query
    
    # Если есть поисковый запрос, фильтруем игры по имени ИЛИ по ID
    if search_query:
        query = query.filter(
            db.or_(
                Game.name.ilike(f'%{search_query}%'),
                Game.game_id.ilike(f'%{search_query}%')
            )
        )
    
    # Сортируем по имени и добавляем пагинацию
    games = query.order_by(Game.name.asc()).paginate(
        page=page,
        per_page=50,
        error_out=False
    )
    
    # Получаем общее количество найденных игр
    total_games = query.count()
    
    return render_template(
        'gamelist.html',
        games=games,
        total_games=total_games,
        search_query=search_query
    )

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
@app.route('/admin/games/delete/<game_id>', methods=['POST'])
@admin_required
def delete_game(game_id):
    try:
        game = Game.query.filter_by(game_id=game_id).first()
        
        if not game:
            return jsonify({'success': False, 'error': 'Game not found'}), 404
        
        # Удаляем файл игры, если он существует
        if game.file_path and os.path.exists(game.file_path):
            try:
                os.remove(game.file_path)
            except OSError as e:
                app.logger.error(f'Error deleting game file: {str(e)}')
        
        # Удаляем запись из базы данных
        db.session.delete(game)
        db.session.commit()
        
        flash('Игра успешно удалена', 'success')
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting game: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/admin/games/edit/<game_id>', methods=['GET', 'POST'])
@admin_required
def edit_game(game_id):
    game = Game.query.filter_by(game_id=game_id).first_or_404()
    
    # Получаем список всех изображений из директории
    images_dir = os.path.join('app', 'static', 'images')
    available_images = []
    if os.path.exists(images_dir):
        available_images = [
            f'/static/images/{f}' for f in os.listdir(images_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ]
    
    if request.method == 'POST':
        game.name = request.form['name']
        game.developer = request.form['developer']
        game.release_date = request.form['release_date']
        
        # Обработка выбора изображения
        selected_image = request.form.get('image_path')
        if selected_image and selected_image != 'custom_url':
            game.path = selected_image
        else:
            custom_url = request.form.get('image_url')
            if custom_url:
                game.path = custom_url

        game.windows = 'windows' in request.form
        game.mac = 'mac' in request.form
        game.linux = 'linux' in request.form
        game.access_type = request.form['access']
        game.drm_notice = request.form['drm_notice']
        
        dlc_text = request.form.get('dlc', '')
        if dlc_text:
            game.dlc = json.dumps([d.strip() for d in dlc_text.split('\n') if d.strip()])
        else:
            game.dlc = None

        try:
            db.session.commit()
            flash('Игра успешно обновлена!', 'success')
            return redirect(url_for('admin_games'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при обновлении игры: {str(e)}', 'error')

    return render_template('admin/edit_game.html', 
                         game=game, 
                         available_images=available_images)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        users = User.load_users()
        user_data = users.get(username)
        
        if user_data and check_password_hash(user_data['password_hash'], password):
            user = User(username)
            user.is_admin = user_data.get('is_admin', False)  # Явно устанавливаем права админа
            login_user(user, remember=True)
            
            # Логируем успешный вход
            app.logger.info(f'Successful login for user: {username}')
            
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('home')
                
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(next_page)
        else:
            flash('Неверное имя пользователя или пароль', 'error')
            app.logger.warning(f'Failed login attempt for user: {username}')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
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

def validate_file(file):
    if not file:
        return False
    filename = secure_filename(file.filename)
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

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Серверная ошибка: {error}')
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403 

@app.errorhandler(Exception)
def handle_error(error):
    app.logger.error(f'Необработанная ошибка: {str(error)}')
    return render_template('error.html', error=error), 500 

@cache.memoize(timeout=300)
def get_game_stats():
    return {
        'total_games': Game.query.count(),
        'active_users': ActiveUsers.get_active_count()
    } 

@cache.memoize(timeout=300)
def get_game_details(game_id):
    return Game.query.filter_by(game_id=game_id).first() 