from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
import mimetypes
import json
import urllib.parse
import pathlib
import socket
import logging

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# Конфігурація
uri = "mongodb://mongodb:27017"
HTTPServer_Port = 3000
UDP_IP = '127.0.0.1'
UDP_PORT = 5000


# Клас для обробки HTTP-запитів
class HttpGetHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        logging.info(f"Отримано GET запит: {self.path}")
        if self.path == "/" or self.path == "/index.html":
            self.send_html_file("static/index.html")
        elif self.path == "/message.html":
            self.send_html_file("static/message.html")
        elif self.path.startswith("/static/"):
            self.send_static()
        else:
            self.send_html_file("static/error.html", status_code=404)

    def do_POST(self):
        logging.info(f"Отримано POST запит: {self.path}")
        if self.path == "/send_message":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            parsed_data = urllib.parse.parse_qs(post_data.decode())
            message_data = {
                "username": parsed_data.get('username', [''])[0],
                "message": parsed_data.get('message', [''])[0],
                "date": str(datetime.now())
            }

            # Відправляємо дані через сокети
            send_data_to_socket(json.dumps(message_data).encode())
            self.send_html_file("static/index.html")

    def send_html_file(self, filename, status_code=200):
        try:
            with open(filename, 'rb') as file:
                self.send_response(status_code)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_html_file("static/error.html", status_code=404)

    def send_static(self):
        file_path = pathlib.Path(self.path[1:])  # видаляємо перший символ '/'
        if file_path.exists():
            self.send_response(200)
            mime_type, _ = mimetypes.guess_type(str(file_path))
            self.send_header('Content-type', mime_type or 'application/octet-stream')
            self.end_headers()
            with open(file_path, 'rb') as file:
                self.wfile.write(file.read())
        else:
            self.send_html_file("static/error.html", status_code=404)

# Запуск HTTP сервера
def run_http_server(server_class=HTTPServer, handler_class=HttpGetHandler):
    server_address = ('0.0.0.0', HTTPServer_Port)
    http = server_class(server_address, handler_class)
    logging.info(f"HTTP сервер запущено на порту {HTTPServer_Port}")
    
    try:
        http.serve_forever()
    except Exception as e:
        logging.error(f"Помилка в HTTP сервері: {e}")
    finally:
        http.server_close()

# Відправка даних через сокет (UDP)
def send_data_to_socket(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = UDP_IP, UDP_PORT
    try:
        sock.sendto(data, server)
        logging.info(f"Дані відправлено на сокет-сервер: {data}")
    except Exception as e:
        logging.error(f"Помилка при відправці на сокет-сервер: {e}")
    finally:
        sock.close()

# Збереження даних у MongoDB
def save_data(data):
    client = MongoClient(uri, server_api=ServerApi("1"))
    db = client['message_database']
    collection = db['messages']

    try:
        message = json.loads(data.decode())
        message['date'] = str(datetime.now())
        collection.insert_one(message)
        logging.info(f"Дані збережено в базі: {message}")
    except Exception as e:
        logging.error(f"Помилка при збереженні в MongoDB: {e}")

# Запуск сокет-сервера
def run_socket_server(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    sock.bind(server)
    logging.info(f"Socket-сервер запущено на {ip}:{port}")

    while True:
        try:
            data, _ = sock.recvfrom(1024)
            logging.info(f"Отримано дані: {data}")
            save_data(data)
        except Exception as e:
            logging.error(f"Помилка в сокет-сервері: {e}")
        finally:
            sock.close()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

    # Процеси для HTTP та сокет-серверів
    http_server_process = Process(target=run_http_server)
    socket_server_process = Process(target=run_socket_server, args=(UDP_IP, UDP_PORT))

    http_server_process.start()
    logging.info("HTTP сервер запущено в окремому процесі.")
    
    socket_server_process.start()
    logging.info("Socket сервер запущено в окремому процесі.")
    
    http_server_process.join()
    socket_server_process.join()
