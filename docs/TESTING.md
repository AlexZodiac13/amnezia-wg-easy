# Бот тестирование и примеры

## 🧪 Локальное тестирование

### Требования для тестирования
- Python 3.11+
- PostgreSQL 16+ (или использовать Docker)
- Telegram Bot Token

### Setup для тестирования

```bash
# 1. Установить зависимости
pip install -r bot/requirements.txt
pip install pytest pytest-asyncio python-dotenv

# 2. Создать .env.test
cat > .env.test << EOF
TELEGRAM_BOT_TOKEN=YOUR_TOKEN
ADMIN_TELEGRAM_ID=YOUR_ID
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=test_bot
POSTGRES_USER=test_user
POSTGRES_PASSWORD=test_pass
AWG_INTERFACE=awg0
AWG_LISTEN_PORT=5066
SCRIPTS_DIR=./awg/scripts
CONFIGS_DIR=./awg/data/clients
EOF

# 3. Запустить PostgreSQL (Docker)
docker run --rm -d \
  -e POSTGRES_DB=test_bot \
  -e POSTGRES_USER=test_user \
  -e POSTGRES_PASSWORD=test_pass \
  -p 5432:5432 \
  postgres:16-alpine
```

## 🚀 Запуск бота в Docker

### 1. Build
```bash
docker compose build bot
```

### 2. Run
```bash
docker compose up -d bot postgres
```

### 3. Проверить логи
```bash
docker compose logs -f bot
```

### 4. Проверить БД
```bash
docker compose exec postgres psql -U bot_user -d amnezia_bot -c "SELECT * FROM users;"
```

## 📱 Тестирование в Telegram

### 1. Найти вашего бота
Открыть Telegram и найти бот по username в @BotFather

### 2. Начинать тестирование

#### Команда /start
```
Expected Output:
🔐 Добро пожаловать в Amnezia VPN Bot!

Привет, [YourName]! 👋

Ваш Telegram ID: `[ID]`

[Меню с кнопками]
```

#### Команда /info
```
Expected Output:
ℹ️ Информация о вашем аккаунте

Telegram ID: `[ID]`
Статус: 👤 Пользователь

Текущая конфигурация:
Нет активной конфигурации.
```

#### Кнопка "📝 Получить конфиг"
```
Expected Output:
📋 У вас уже есть активный конфиг. Создать новый?

[Кнопка: ✅ Да, создать новый]
[Кнопка: ❌ Нет, показать текущий]
```

#### Нажать "✅ Да, создать новый"
```
Expected Sequence:
1. ⏳ Создаю конфиг...
2. ✅ Конфиг успешно создан!
3. Текст конфига (```text```)
4. QR-код (фото)
5. Файл конфига (.conf)
6. JSON бекап (амнезия)
7. Инструкция
```

## 🔧 Тестирование API функционала

### Тест создания пира
```bash
curl -X POST http://localhost:8000/api/peers \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "test_client",
    "client_ip": "10.80.0.100",
    "rate_limit": 20
  }'
```

### Тест БД
```bash
# Подключиться к БД
docker compose exec postgres psql -U bot_user -d amnezia_bot

# Проверить таблицы
\dt

# Проверить пользователей
SELECT * FROM users;

# Проверить конфиги
SELECT * FROM configs;

# Проверить уведомления
SELECT * FROM notification_logs;
```

## 📊 Пример данных в БД

```sql
-- Пример пользователя
INSERT INTO users (telegram_id, username, is_admin, created_at, updated_at)
VALUES (123456789, 'testuser', false, NOW(), NOW());

-- Пример конфига
INSERT INTO configs 
(config_id, user_id, client_name, client_private_key, client_public_key, 
 client_preshared_key, client_ip, rate_limit, expires_at, is_active, 
 wg_config_content, created_at)
VALUES 
('550e8400-e29b-41d4-a716-446655440000', 1, 'tg_123456789_1234567890',
 'wJk...', 'zXy...', 'aBc...', '10.80.0.11', 15,
 NOW() + INTERVAL '30 days', true, '[конфиг текст]', NOW());
```

## 🐛 Отладка

### Включить DEBUG логирование
```python
# В main.py
logging.basicConfig(level=logging.DEBUG)
```

### Просмотр событий БД
```bash
docker compose exec postgres psql -U bot_user -d amnezia_bot

# Включить query logging
SET log_statement = 'all';
```

### Проверить сетевое подключение
```bash
# Проверить, может ли бот подключиться к БД
docker compose exec bot python -c "
import asyncio
from src.database.db import check_db_connection
print(asyncio.run(check_db_connection()))
"
```

## 📈 Нагрузочное тестирование

### Симуляция множества пользователей
```python
# test_load.py
import asyncio
import random
from src.database.db import init_db, async_session
from src.services.database_service import DatabaseService

async def test_create_many_users():
    await init_db()
    
    async with async_session() as session:
        for i in range(100):
            await DatabaseService.create_user(
                session,
                telegram_id=random.randint(1000000, 9999999),
                username=f"user_{i}"
            )
        
        count = await DatabaseService.get_user_count(session)
        print(f"Created {count} users")

asyncio.run(test_create_many_users())
```

Запуск:
```bash
cd bot
python test_load.py
```

## 🔄 Тестирование автоматизаций

### Тест нотификаций об истечении
```bash
# Перейти на дату близкую к истечению
docker compose exec postgres psql -U bot_user -d amnezia_bot -c "
UPDATE configs SET expires_at = NOW() + INTERVAL '2 days' WHERE id = 1;
"

# Запустить планировщик вручную
docker compose logs -f bot | grep "expiring"
```

### Тест удаления истекших конфигов
```bash
# Создать истекший конфиг
docker compose exec postgres psql -U bot_user -d amnezia_bot -c "
UPDATE configs SET expires_at = NOW() - INTERVAL '1 day' WHERE id = 1;
"

# Проверить логи удаления
docker compose logs bot | grep "Deleted expired"
```

## ✅ Чек-лист тестирования

- [ ] Бот запускается и подключается к БД
- [ ] /start создает нового пользователя
- [ ] /info показывает информацию об аккаунте
- [ ] Кнопка "Получить конфиг" работает
- [ ] Конфиг содержит валидный WireGuard текст
- [ ] QR-код генерируется корректно
- [ ] JSON бекап Amnezia формирует правильно
- [ ] Конфиг сохраняется в БД
- [ ] Конфиг экспирирует через 30 дней
- [ ] Нотификация отправляется за 3 дня
- [ ] Истекший конфиг удаляется автоматически
- [ ] Админ видит список пользователей
- [ ] Админ может удалить пользователя
- [ ] Обработка ошибок работает
- [ ] Логи записываются корректно

## 🚨 Частые ошибки

### "Database connection refused"
```
Решение: Убедиться, что postgres запущен
docker compose ps postgres
```

### "No such file or directory: awg/scripts/add-peer.sh"
```
Решение: Скрипты должны быть в ./awg/scripts/
Проверить: ls -la awg/scripts/
```

### "Bot token is invalid"
```
Решение: Проверить TELEGRAM_BOT_TOKEN в .env
Получить новый у @BotFather
```

### "Peer already exists"
```
Решение: Удалить старый конфиг перед созданием нового
docker compose exec awg wg show
```

## 📚 Дополнительные ресурсы

- [aiogram docs](https://docs.aiogram.dev/)
- [SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [PostgreSQL docs](https://www.postgresql.org/docs/)
- [WireGuard manual](https://www.wireguard.com/quickstart/)

## 🎯 Следующие шаги

1. Развернуть на продакшене
2. Настроить SSL/TLS
3. Добавить备份 автоматическую
4. Реализовать rate limiting Telegram API
5. Добавить веб-панель администратора
6. Интеграция с платежными системами
