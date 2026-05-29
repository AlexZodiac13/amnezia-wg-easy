FROM python:3.11-slim

WORKDIR /app

# Установить зависимости системы
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wireguard-tools \
    && rm -rf /var/lib/apt/lists/*

# Скопировать зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопировать код приложения
COPY . .

# Установить переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Запуск бота
CMD ["python", "main.py"]
