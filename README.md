# AmneziaWG Admin

Минимальная админ-панель для AmneziaWG с веб-интерфейсом, JSON API и локальной SQLite-базой.

## Что уже есть

- вход только под админом
- список peers
- создание peer с генерацией ключей
- QR-код и готовый конфиг
- включение/выключение и удаление peer
- API для будущего Telegram-бота

## Запуск

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Или через Docker:

```bash
docker compose up --build
```

## Переменные окружения

- `ADMIN_USERNAME` - имя администратора
- `ADMIN_PASSWORD` - пароль администратора
- `SECRET_KEY` - секрет для cookie-сессий
- `DATABASE_PATH` - путь к SQLite базе
- `SERVER_ENDPOINT_HOST` - внешний адрес сервера
- `SERVER_ENDPOINT_PORT` - внешний порт

## Важное

Сейчас это control plane и веб-панель. Следующий шаг - подключить реальное применение конфигурации на хосте, когда будет подтверждено, как именно вы хотите поднимать AmneziaWG в контейнере или на сервере.
