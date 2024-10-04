import logging
import mimetypes
import socket
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from multiprocessing import Process
from urllib.parse import unquote_plus, urlparse

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

#Задаємо змінні
DB_URI = "mongodb://mongodb:27017"
FRONT_FOLDER = "static"
BASE_DIR = Path(__file__).parent / "static"
CHUNK_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000
HTTP_HOST = "0.0.0.0"
SOCKET_HOST = "127.0.0.1"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(process)s - %(message)s"
)

# Клас для обробки HTTP-запитів
class HttpGetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        router = urlparse(self.path).path
        match router:
            case "/":
                self.send_html(f"{FRONT_FOLDER}/index.html")
            case "/message.html":
                self.send_html(f"{FRONT_FOLDER}/message.html")
            case _:
                file = BASE_DIR.joinpath(router[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html(f"{FRONT_FOLDER}/error.html", 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        try:
            socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_client.sendto(data, (SOCKET_HOST, SOCKET_PORT))
            socket_client.close()
        except socket.error:
            logging.error("Failed to send data")
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        self.send_response(status)
        mt = mimetypes.guess_type(filename)[0] or "text/plain"
        self.send_header("Content-Type", mt)
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())

# Запуск HTTP сервера
def run_http_server(host, port):
    try:
        httpd = HTTPServer((host, port), HttpGetHandler)
        logging.info(f"Server running on http://{host}:{port}")
        httpd.serve_forever()
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("Server stopped")
        httpd.server_close()

# Запуск socket сервера
def run_socket_server(host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((host, port))
    logging.info(f"Socket server started on ws://{host}:{port}")
    try:
        while True:
            data, addr = server.recvfrom(CHUNK_SIZE)
            logging.info(f"Received data from {addr}:{data.decode()}")
            save_to_db(data.decode())
    except Exception as e:
        logging.error(e)
    finally:
        logging.info("Socket server stopped")
        server.close()

# Збереження повідомлень до бази
def save_to_db(data):
    client = MongoClient(DB_URI, server_api=ServerApi("1"))
    db = client.homework
    try:
        data_parse = unquote_plus(data)
        data_dict = {
            key: value for key, value in [el.split("=") for el in data_parse.split("&")]
        }
        document = {"date": datetime.now().strftime('"%Y-%m-%d %H:%M:%S.%f"')}
        document.update(data_dict)
        db.messages.insert_one(document)

    except Exception as e:
        logging.error("DB error", e)
    finally:
        client.close()


def main():
    http_server = Process(
        target=run_http_server,
        args=(HTTP_HOST,HTTP_PORT,),
        name="http_server",
    )
    socket_server = Process(
        target=run_socket_server,
        args=(SOCKET_HOST,SOCKET_PORT,),
        name="socket_server",
    )

    http_server.start()
    socket_server.start()

    try:
        http_server.join()
        socket_server.join()
    finally:
        http_server.terminate()
        socket_server.terminate()
        http_server.join()
        socket_server.join()
        logging.info("Server stopped")


if __name__ == "__main__":
    main()
