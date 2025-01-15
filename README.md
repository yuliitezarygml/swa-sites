# SWA Game Service

Система управления играми для **SWA V2**.

---

## Установка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <url-репозитория>
   cd swa-game-service
   ```
2. **Создайте виртуальное окружение:**
   ```bash
   python -m venv venv
   ```
3. **Активируйте виртуальное окружение:**
   - **Windows:**
     ```bash
     venv\Scripts\activate
     ```
   - **Linux/Mac:**
     ```bash
     source venv/bin/activate
     ```
4. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Настройка базы данных

1. **Инициализация базы данных:**
   ```bash
   flask db init
   ```
2. **Создание миграции:**
   ```bash
   flask db migrate -m "Initial migration"
   ```
3. **Применение миграции:**
   ```bash
   flask db upgrade
   ```

---

## Создание администратора

Запустите скрипт для создания администратора:
```bash
python create_admin.py
```

**Учетные данные по умолчанию:**
- Логин: `admin`
- Пароль: `admin123`

---

## Запуск приложения

1. **Для разработки:**
   ```bash
   python run.py
   ```
2. **Для production (с помощью Gunicorn):**
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 run:app
   ```

---

## Структура проекта

```plaintext
swa-game-service/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   ├── models.py
│   ├── config.py
│   └── templates/
│       ├── admin/
│       │   ├── games.html
│       │   ├── add_game.html
│       │   ├── edit_game.html
│       │   └── file_browser.html
│       ├── base.html
│       └── ...
├── instance/
│   ├── base.txt
│   └── statistics.txt
├── migrations/
├── venv/
├── requirements.txt
├── run.py
├── create_admin.py
└── README.md
```

---

## Основные функции

1. **Управление играми:**
   - Добавление новых игр
   - Редактирование существующих игр
   - Удаление игр
   - Управление DLC

2. **Файловый менеджер:**
   - Просмотр файлов
   - Редактирование текстовых файлов
   - Загрузка файлов
   - Удаление файлов

3. **Управление пользователями:**
   - Создание новых пользователей
   - Назначение администраторов

---

## Конфигурация

Основные настройки находятся в файле `app/config.py`:
- `SECRET_KEY`: ключ для сессий
- `SQLALCHEMY_DATABASE_URI`: путь к базе данных
- `MAX_CONTENT_LENGTH`: максимальный размер загружаемых файлов

---

## Создание папок

Создайте необходимые директории:
```bash
mkdir downloads
mkdir fetch_gameid
mkdir static
mkdir instance
mkdir migrations
```

---

## Обновление базы данных

При изменении моделей:
```bash
flask db migrate -m "Описание изменений"
flask db upgrade
```

---

## Сброс базы данных

Если нужно пересоздать базу:
```bash
rm instance/database.db
flask db upgrade
python create_admin.py
```

---

## Резервное копирование

1. **Базы данных:**
   ```bash
   cp instance/database.db backup/database.db.backup
   ```
2. **Файлов конфигурации:**
   ```bash
   cp instance/base.txt backup/base.txt.backup
   cp instance/statistics.txt backup/statistics.txt.backup
   ```

---

## Решение проблем

1. **Ошибка с правами доступа:**
   ```bash
   chmod -R 755 .
   chmod -R 777 instance
   ```
2. **Не работает загрузка файлов:**
   ```bash
   chmod -R 777 uploads
   chmod -R 777 downloads
   ```

---

## Поддержка

При возникновении проблем создавайте issue в репозитории или обращайтесь к разработчикам.

---

## Лицензия

Проект распространяется под лицензией **MIT License**.
