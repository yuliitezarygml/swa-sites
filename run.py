from app import app
import socket

def get_ip():
    try:
        # Получаем имя х оста
        hostname = socket.gethostname()
        # Получаем IP-адрес
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except:
        return "localhost"

if __name__ == '__main__':
    ip = get_ip()
    port = 5000  # Стандартный порт Flask
    
    print("\n=== API URLs ===")
    print(f"API Base URL: http://{ip}:{port}/api/download")
    print(f"Game ID URL: http://{ip}:{port}/api/gameid/{{gameId}}.zip")
    print(f"Stats URL: http://{ip}:{port}/api/stats")
    print(f"Version URL: http://{ip}:{port}/static/version.json")
    print("==============\n")
    
    app.run(host='0.0.0.0', port=port, debug=True) 
