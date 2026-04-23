# Amnezia WG Easy - VPN Management with Telegram Bot

Это полнофункциональное решение для управления VPN сервером AmneziaWG с помощью Telegram бота.

## 🚀 Основные возможности

### 🔐 VPN управление
- ✅ Автоматическое создание конфигов WireGuard через Telegram
- ✅ QR-коды для мобильных приложений
- ✅ Экспорт конфигов в формате WireGuard
- ✅ Бекапы для приложения Amnezia (JSON)
- ✅ Управление пирами через скрипты

### ⏰ Управление сроком действия
- ✅ Автоматическое истечение конфигов (30 дней по умолчанию)
- ✅ Уведомления за 3 дня до истечения срока
- ✅ Автоматическое удаление истекших конфигов
- ✅ Возобновление конфигов по требованию

### 👥 Управление пользователями
- ✅ Система администраторов
- ✅ Отслеживание активных пользователей
- ✅ Удаление пользователей и конфигов
- ✅ Статистика использования

### 🔄 Ограничение скорости
- ✅ Per-peer ограничение пропускной способности (tc + iptables)
- ✅ Сохранение ограничений при перезагрузке контейнера
- ✅ Конфигурируемые лимиты по умолчанию

## 📋 Архитектура

```
┌─────────────────────┐
│  Telegram User      │
│  @YourBotName       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Bot Service        │
│  (aiogram 3.4)      │
│  Python 3.11        │
└──────┬──────────────┘
       │
    ┌──▼────────────────┐
    │                   │
    ▼                   ▼
┌─────────────┐   ┌──────────────┐
│ PostgreSQL  │   │ AmneziaWG    │
│  Database   │   │  VPN Core    │
└─────────────┘   └──────────────┘
```

## 🛠️ Стек технологий

### Backend
- **Python 3.11** - основной язык
- **aiogram 3.4.1** - Telegram API framework
- **asyncpg** - асинхронный драйвер PostgreSQL
- **SQLAlchemy 2.0** - ORM
- **APScheduler** - планировщик задач

### VPN
- **AmneziaWG** - WireGuard fork с обфускацией
- **tc (HTB)** - управление пропускной способностью
- **iptables** - фильтрация трафика

### Infrastructure
- **PostgreSQL 16** - база данных
- **Docker** - контейнеризация
- **Docker Compose** - оркестрация

## 📦 Установка

### Требования
- Docker & Docker Compose
- Telegram Bot Token (от @BotFather)
- Ваш Telegram ID

### Шаг 1: Клонирование
```bash
git clone https://github.com/yourusername/amnezia-wg-easy.git
cd amnezia-wg-easy
```

### Шаг 2: Конфигурация
```bash
cp .env.bot .env
nano .env  # Отредактировать переменные
```

Заполнить:
- `TELEGRAM_BOT_TOKEN` - токен от @BotFather
- `ADMIN_TELEGRAM_ID` - ваш Telegram ID
- `POSTGRES_PASSWORD` - безопасный пароль БД

### Шаг 3: Запуск
```bash
docker compose up -d
```

### Шаг 4: Проверка
```bash
docker compose logs -f bot
```

Должно вывести:
```
Bot commands set
Initializing database...
Starting notification scheduler...
Starting bot polling...
```

## 🎮 Использование

### Команды для пользователей
```
/start           - Начало работы
/config          - Получить/создать конфиг
/info            - Информация о аккаунте
/help            - Справка
```

### Кнопки интерфейса
- 📝 **Получить конфиг** - Создать новый VPN конфиг
- ℹ️ **Информация** - Показать инфо об аккаунте
- 🆘 **Поддержка** - Информация о поддержке
- 👥 **Количество пользователей** - Статистика (админ)
- 📋 **Список пользователей** - Все пользователи (админ)

### Администраторские команды
```
/delete_user <id> - Удалить пользователя
/users            - Список пользователей
/stats            - Статистика
```

## 🔧 Конфигурация

### Переменные окружения (.env)

```env
# Telegram
TELEGRAM_BOT_TOKEN=123:ABC...
ADMIN_TELEGRAM_ID=12345678

# Database
POSTGRES_DB=amnezia_bot
POSTGRES_USER=bot_user
POSTGRES_PASSWORD=your_secure_password

# VPN Settings
AWG_INTERFACE=awg0
AWG_LISTEN_PORT=5066
AWG_SUBNET=10.80.0.1/24
AWG_DNS=10.80.0.1

# Bot Settings
DEFAULT_RATE_LIMIT=15           # Mbit/s
EXPIRATION_DAYS=30              # дней
NOTIFICATION_DAYS=3             # за N дней до истечения
```

## 📊 Структура БД

### Таблица: users
```sql
- id (PRIMARY KEY)
- telegram_id (UNIQUE)
- username
- is_admin
- created_at
- updated_at
```

### Таблица: configs
```sql
- id (PRIMARY KEY)
- config_id (UUID, UNIQUE)
- user_id (FOREIGN KEY)
- client_name
- client_private_key
- client_public_key
- client_preshared_key
- client_ip
- rate_limit (Mbit/s)
- wg_config_content
- expires_at
- notified_at
- is_active
- created_at
```

### Таблица: notification_logs
```sql
- id (PRIMARY KEY)
- config_id
- user_id
- notification_type
- sent_at
```

## 🐛 Troubleshooting

### Bot не отвечает
```bash
docker compose logs bot
```

### Проблемы с БД
```bash
docker compose logs postgres
```

### Ошибки VPN
```bash
docker compose logs awg
```

### Полный ресет
```bash
docker compose down -v
docker compose up -d
```

### Очистить БД
```bash
docker compose exec postgres psql -U bot_user -d amnezia_bot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

## 🔐 Безопасность

- ✅ Все пароли конфигурируются через .env
- ✅ Сессии БД используют async для безопасности
- ✅ Логирование всех действий администраторов
- ✅ Изоляция сетей Docker для микросервисов
- ✅ Шифрование трафика через WireGuard

## 📈 Производительность

- Поддержка до 100+ одновременных подключений
- Оптимизированные SQL запросы с индексами
- Асинхронная архитектура Python
- Connection pooling для БД
- Параллельные задачи планировщика

## 🚀 Развертывание

### На сервере
```bash
# Клонировать
git clone https://github.com/yourusername/amnezia-wg-easy.git
cd amnezia-wg-easy

# Настроить
cp .env.bot .env
# Отредактировать .env со своими значениями

# Запустить
docker compose up -d

# Проверить
docker compose ps
docker compose logs -f
```

### Обновление
```bash
git pull
docker compose down
docker compose up -d
```

## 📝 Лицензия

MIT License

## 👨‍💻 Разработка

### Структура проекта
```
.
├── awg/                    # VPN core
│   ├── Dockerfile
│   ├── entrypoint.sh      # Rate limit restoration
│   ├── scripts/           # Peer management
│   └── data/              # Persistent storage
│
├── dnsmasq/               # DNS service
│   └── ...
│
├── bot/                   # Telegram bot
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── config.py      # Settings
│       ├── database/      # ORM models
│       ├── handlers/      # Command handlers
│       ├── services/      # Business logic
│       └── scheduler.py   # Task scheduler
│
├── docker-compose.yml     # Orchestration
└── .env.bot              # Config template
```

### Разработка локально
```bash
# Установить зависимости
pip install -r bot/requirements.txt

# Установить pre-commit hooks
pre-commit install

# Запустить тесты
pytest

# Линтинг
flake8 bot/
mypy bot/
```

## 🤝 Вклад

Приветствуются Pull Requests!

## 📞 Поддержка

- 📧 Email: support@example.com
- 🐛 Issues: GitHub Issues
- 💬 Chat: Telegram @supportbot

---

**Создано для упрощения управления VPN сервером через Telegram** 🚀
