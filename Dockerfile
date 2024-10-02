# Використовуємо базовий образ Python
FROM python:3.10-slim

# Встановлюємо необхідні системні залежності
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Створюємо робочу директорію
WORKDIR /app

# Копіюємо всі файли до контейнера
COPY . /app

# Копіюємо папку static до контейнера
COPY static /app/static

# Встановлюємо залежності Python
RUN pip install --no-cache-dir -r requirements.txt

# Експортуємо порти для HTTP та сокет-сервера
EXPOSE 3000 5000

# Вказуємо команду для запуску програми
CMD ["python", "main.py"]