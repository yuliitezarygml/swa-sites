from app import app, db
from app.models import Game
import json
import os
import logging
import requests
from urllib.parse import urlparse
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
IMAGES_DIR = os.path.join('app', 'static', 'images')
DEFAULT_IMAGE = 'default-game.png'

def download_image(url, game_id):
    """Скачивание и сохранение изображения"""
    if not url:
        return ''
    
    try:
        # Создаем директорию для изображений, если её нет
        os.makedirs(IMAGES_DIR, exist_ok=True)
        
        # Получаем расширение файла из URL
        ext = os.path.splitext(urlparse(url).path)[1]
        if not ext:
            ext = '.jpg'  # Используем .jpg по умолчанию
        
        # Формируем имя файла
        filename = f"{game_id}{ext}"
        filepath = os.path.join(IMAGES_DIR, filename)
        
        # Проверяем, существует ли файл
        if os.path.exists(filepath):
            return f'/static/images/{filename}'
        
        # Скачиваем изображение
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Сохраняем изображение
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Successfully downloaded image for game {game_id}")
        return f'/static/images/{filename}'
        
    except Exception as e:
        logger.error(f"Error downloading image for game {game_id}: {str(e)}")
        return ''

def clear_database():
    """Очистка базы данных от всех игр"""
    try:
        with app.app_context():
            games_count = Game.query.count()
            Game.query.delete()
            db.session.commit()
            logger.info(f"Successfully deleted {games_count} games from database")
            
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error clearing database: {str(e)}")
        raise

def import_games_from_json():
    """Импорт игр из JSON файла"""
    json_path = os.path.join(os.path.expanduser('~'), 'Downloads', 'all_games_transformed.json')
    
    try:
        # Очищаем базу данных
        logger.info("Starting database cleanup...")
        clear_database()
        logger.info("Database cleanup completed")
        
        # Читаем JSON файл
        logger.info(f"Reading JSON file from {json_path}")
        with open(json_path, 'r', encoding='utf-8') as file:
            games_data = json.load(file)
        
        logger.info(f"Found {len(games_data)} games in JSON file")
        
        with app.app_context():
            added_count = 0
            error_count = 0
            image_error_count = 0
            
            for game_id, game_info in games_data.items():
                try:
                    # Скачиваем изображение
                    image_url = game_info.get('image', '')
                    image_path = download_image(image_url, game_id)
                    
                    if not image_path and image_url:
                        image_error_count += 1
                    
                    # Определяем платформы
                    platforms = game_info.get('platforms', '').lower().split(', ')
                    
                    # Создаем новую запись игры
                    new_game = Game(
                        game_id=str(game_info['game_id']),
                        name=game_info['name'],
                        developer=game_info.get('developer', ''),
                        release_date=game_info.get('release_date', ''),
                        path=image_path or '/static/default-game.png',  # Используем путь к скачанному изображению или дефолтное
                        windows='windows' in platforms,
                        mac='mac' in platforms,
                        linux='linux' in platforms,
                        dlc=game_info.get('dlc', ''),
                        access_type=game_info.get('access', 'paid'),
                        drm_notice=game_info.get('drm_notice', '')
                    )
                    
                    db.session.add(new_game)
                    
                    # Коммит каждые 100 игр
                    added_count += 1
                    if added_count % 100 == 0:
                        db.session.commit()
                        logger.info(f"Progress: {added_count} games imported")
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error adding game {game_info.get('name', 'Unknown')}: {str(e)}")
            
            # Финальный коммит
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error in final commit: {str(e)}")
            
            # Итоговая статистика
            logger.info("\nImport completed!")
            logger.info(f"Added games: {added_count}")
            logger.info(f"Errors: {error_count}")
            logger.info(f"Image download errors: {image_error_count}")
            logger.info(f"Total processed: {added_count + error_count}")
            
            final_count = Game.query.count()
            logger.info(f"Total games in database: {final_count}")
            
    except FileNotFoundError:
        logger.error(f"Error: File not found at {json_path}")
    except json.JSONDecodeError:
        logger.error("Error: Invalid JSON format")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == '__main__':
    print("Starting games import process...")
    # Добавляем requests в requirements.txt если его там нет
    try:
        import requests
    except ImportError:
        logger.error("Please install requests: pip install requests")
        exit(1)
    
    import_games_from_json() 