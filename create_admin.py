import os
import json
from werkzeug.security import generate_password_hash

# Создаем директорию instance если её нет
if not os.path.exists('instance'):
    os.makedirs('instance')

# Создаем новый файл base.txt с учетными данными администратора
admin_data = {
    "admin": {
        "password_hash": generate_password_hash("admin123"),
        "is_admin": True
    }
}

with open('instance/base.txt', 'w') as f:
    json.dump(admin_data, f, indent=4)

print("Admin account created successfully!")
print("Username: admin")
print("Password: admin123") 