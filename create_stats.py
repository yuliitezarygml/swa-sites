import os
import json

# Создаем директорию instance если её нет
if not os.path.exists('instance'):
    os.makedirs('instance')

# Создаем файл статистики с начальными данными
initial_stats = {
    "total_visits": 0
}

with open('instance/statistics.txt', 'w') as f:
    json.dump(initial_stats, f, indent=4)

print("Statistics file created successfully!") 