# 📁 Структура проекта Amnezia VPN Bot

## Полная иерархия файлов

```
amnezia-wg-easy/
│
├── 📄 README.md                          ⭐ Основной README (обновлен с инфо о боте)
├── 📄 README_BOT.md                      📖 Полная документация по боту
├── 📄 BOT_SETUP.md                       🛠️ Инструкция по настройке бота
├── 📄 TESTING.md                         🧪 Инструкции по тестированию
├── 📄 PROJECT_SUMMARY.md                 📊 Итоговое резюме проекта
├── 📄 IMPLEMENTATION_CHECKLIST.md        ✅ Чек-лист реализации
├── 📄 docker-compose.yml                 🐳 Оркестрация сервисов
│
├── 📄 .env.bot                           ⚙️ Шаблон переменных окружения
│
│
├── 🔵 awg/                               VPN ядро (AmneziaWG)
│   ├── Dockerfile                        Container для VPN
│   ├── entrypoint.sh                     🔧 Восстановление rate limits
│   ├── 📁 data/                          Persistent storage
│   │   ├── clients/                      WireGuard конфиги клиентов
│   │   └── awg0.conf                     Конфиг интерфейса
│   │
│   └── 📁 scripts/                       Управление пирами
│       ├── add-peer.sh                   ➕ Добавить пира
│       ├── remove-peer.sh                ➖ Удалить пира
│       └── list-peers.sh                 📋 Список пиров
│
│
├── 🟠 dnsmasq/                           DNS сервис
│   ├── Dockerfile
│   ├── dnsmasq.conf
│   └── lists/
│
│
└── 🟣 bot/                               Telegram Bot 🤖
    │
    ├── 📄 main.py                        ⭐ Точка входа (aiogram + asyncio)
    ├── 📄 Dockerfile                     Container для бота
    ├── 📄 requirements.txt                🔧 Python зависимости
    ├── 📄 .env.example                   ⚙️ Шаблон .env
    ├── 📄 .gitignore                     🔒 Git исключения
    │
    └── 📁 src/                           Исходный код
        │
        ├── 📄 __init__.py                Package marker
        ├── 📄 config.py                  ⚙️ Загрузка конфигурации
        ├── 📄 scheduler.py               ⏱️ APScheduler для уведомлений
        │
        ├── 📁 database/                  БД слой
        │   ├── 📄 __init__.py
        │   ├── 📄 db.py                  🔌 AsyncPG + SQLAlchemy
        │   └── 📄 models.py              📊 ORM модели
        │
        ├── 📁 handlers/                  Telegram обработчики
        │   ├── 📄 __init__.py
        │   ├── 📄 commands.py            📱 Команды бота
        │   └── 📄 config_handlers.py     🔧 Callbacks для конфигов
        │
        └── 📁 services/                  Бизнес-логика
            ├── 📄 __init__.py
            ├── 📄 database_service.py    🗄️ CRUD операции
            ├── 📄 peer_manager.py        🔌 Управление пирами
            └── 📄 config_manager.py      📝 Парсинг и генерация конфигов
```

## 📊 Описание ключевых файлов

### Корневые файлы

| Файл | Описание | Назначение |
|------|---------|-----------|
| `README.md` | Основная документация | Описание всего проекта |
| `docker-compose.yml` | Оркестрация сервисов | Запуск awg, postgres, bot |
| `.env.bot` | Шаблон переменных | Быстрый старт конфигурации |

### VPN (awg/)

| Файл | Строк | Описание |
|------|------|---------|
| `entrypoint.sh` | ~200 | 🔧 Восстановление rate limits при старте |
| `scripts/add-peer.sh` | ~150 | ➕ Создание пира с rate limiting |
| `scripts/remove-peer.sh` | ~50 | ➖ Удаление пира |
| `scripts/list-peers.sh` | ~30 | 📋 Список активных пиров |

### Bot (bot/)

#### Точка входа
| Файл | Строк | Описание |
|------|------|---------|
| `main.py` | ~80 | ⭐ Инициализация, polling, scheduler |
| `Dockerfile` | ~15 | 🐳 Container образ |
| `requirements.txt` | ~15 | 📦 Зависимости |

#### Конфигурация (bot/src/)
| Файл | Строк | Описание |
|------|------|---------|
| `config.py` | ~30 | ⚙️ Загрузка из .env |
| `scheduler.py` | ~120 | ⏰ Уведомления об истечении |

#### База данных (bot/src/database/)
| Файл | Строк | Описание |
|------|------|---------|
| `db.py` | ~50 | 🔌 AsyncPG engine, session factory |
| `models.py` | ~80 | 📊 User, Config, NotificationLog |

#### Обработчики (bot/src/handlers/)
| Файл | Строк | Описание |
|------|------|---------|
| `commands.py` | ~200 | 📱 /start, /info, /config, /help |
| `config_handlers.py` | ~250 | 🔧 Callback buttons для конфигов |

#### Сервисы (bot/src/services/)
| Файл | Строк | Описание |
|------|------|---------|
| `database_service.py` | ~150 | 🗄️ CRUD User, Config, logs |
| `peer_manager.py` | ~100 | 🔌 Интеграция с add-peer.sh |
| `config_manager.py` | ~150 | 📝 QR, парсинг, Amnezia бекап |

## 🔄 Поток данных

### Создание конфига

```
User: /config
  ↓
Bot: Проверить активный конфиг
  ↓
User: Нажать "✅ Создать новый"
  ↓
Bot: Деактивировать старый, удалить пира
  ↓
Bot: Вызвать add-peer.sh с параметрами
  ↓
add-peer.sh: Создать пира в WireGuard + rate limiting
  ↓
add-peer.sh: Сохранить "# Rate = 15" в конфиг
  ↓
Bot: Парсить конфиг, извлечь ключи
  ↓
Bot: Генерировать QR + JSON бекап
  ↓
Bot: Сохранить в БД с expires_at
  ↓
Bot: Отправить все файлы пользователю
```

### Автоматизация (каждый час)

```
APScheduler: Запустить check_expiring_configs()
  ↓
DB: Найти конфиги где expires_at = NOW() + 3 дня
  ↓
Bot: Отправить уведомление каждому пользователю
  ↓
DB: Отметить как notified_at
  ↓
---
  ↓
APScheduler: Запустить delete_expired_configs()
  ↓
DB: Найти конфиги где expires_at < NOW()
  ↓
Bot: Вызвать remove-peer.sh для удаления
  ↓
DB: Деактивировать конфиг
  ↓
Bot: Отправить уведомление об удалении
```

## 🗂️ Организация по функциям

### User Management
- `bot/src/handlers/commands.py` - /start создает пользователя
- `bot/src/database/models.py` - модель User
- `bot/src/services/database_service.py` - CRUD для User

### Config Management  
- `bot/src/handlers/commands.py` - /config команда
- `bot/src/handlers/config_handlers.py` - создание/просмотр
- `bot/src/database/models.py` - модель Config
- `bot/src/services/config_manager.py` - парсинг, QR
- `bot/src/services/database_service.py` - CRUD для Config

### VPN Integration
- `bot/src/services/peer_manager.py` - вызов скриптов
- `awg/scripts/add-peer.sh` - создание пира
- `awg/scripts/remove-peer.sh` - удаление пира
- `awg/entrypoint.sh` - восстановление лимитов

### Notifications
- `bot/src/scheduler.py` - APScheduler
- `bot/main.py` - запуск scheduler
- `bot/src/database/models.py` - NotificationLog
- `bot/src/services/database_service.py` - логирование

## 📦 Зависимости

### Python (bot/requirements.txt)
```
aiogram==3.4.1           # Telegram API
asyncpg==0.29.0          # PostgreSQL драйвер
sqlalchemy==2.0.25       # ORM
python-dotenv==1.0.0     # .env файлы
python-qrcode==7.4.2     # QR коды
pillow==10.1.0           # Изображения
apscheduler==3.10.4      # Планировщик
```

### Docker Services
```
postgres:16-alpine       # БД
python:3.11-slim         # Python контейнер
```

## 🔐 Конфиденциальные данные

### Хранятся в .env
- `TELEGRAM_BOT_TOKEN` - token от @BotFather
- `ADMIN_TELEGRAM_ID` - ID администратора
- `POSTGRES_PASSWORD` - пароль БД
- Порты, пути, лимиты

### Защита
- `.env` в `.gitignore`
- `bot/.env.example` - шаблон без данных
- Никогда не логировать секреты
- Использовать переменные окружения

## 🎯 Запуск компонентов

### Локально (без Docker)
```bash
# PostgreSQL должна быть установлена
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
export TELEGRAM_BOT_TOKEN="your_token"
cd bot
pip install -r requirements.txt
python main.py
```

### В Docker
```bash
docker compose up -d
docker compose logs -f bot
```

### На продакшене
```bash
git clone repo
cd amnezia-wg-easy
cp .env.bot .env
# Отредактировать .env
docker compose -f docker-compose.yml up -d
```

## 📈 Производительность

### Масштабируемость
- Connection pooling: 10 connections, max 20 overflow
- Async обработка сотен запросов в секунду
- Batch операции в БД
- Кэширование где возможно

### Ресурсы
- Bot: ~50MB RAM
- PostgreSQL: ~100MB RAM  
- VPN: ~30MB RAM

---

**Последнее обновление:** 2024-04-22
**Версия:** 1.0.0
**Статус:** Production Ready ✅
