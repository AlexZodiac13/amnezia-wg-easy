# AmneziaWG v2: AWG core

Этот этап поднимает AWG-сервер через `awg-quick` с userspace fallback на `amneziawg-go`.

## Что уже сделано

- Контейнер `awg-core` на базе `awg-quick` и `amneziawg-go`.
- Режим сети: `host`.
- Порт сервера: `51823/udp` (настраивается через env).
- Интерфейс: `awg0`.
- Скрипты управления peer через `awg`:
  - `/opt/awg/scripts/add-peer.sh`
  - `/opt/awg/scripts/remove-peer.sh`
  - `/opt/awg/scripts/list-peers.sh`

Конфиг хранится в `/etc/amnezia/amneziawg/awg0.conf`.
Опционально можно задать `AWG_I1`-`AWG_I5` для signature packets AmneziaWG 2.0; по умолчанию они пустые.

## Запуск

```bash
docker compose up -d --build
docker compose logs -f awg
```

## Проверка интерфейса

```bash
docker exec -it awg-core ip a show awg0
docker exec -it awg-core awg show awg0
```

## Управление peer

Создать клиента и добавить peer с лимитом по умолчанию 15 Мбит:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_NAME> <SERVER_IP_OR_DOMAIN>:51823 10.80.0.2/32
```

Создать клиента с явным лимитом 15 Мбит:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_NAME> <SERVER_IP_OR_DOMAIN>:51823 10.80.0.3/32 "" 15
```

Создать клиента с лимитом 200 Мбит для whitelist-пользователя:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_NAME> <SERVER_IP_OR_DOMAIN>:51823 10.80.0.4/32 "" 200
```

Создать клиента без ограничения скорости:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_NAME> <SERVER_IP_OR_DOMAIN>:51823 10.80.0.5/32 "" 0
```

Если нужен только ручной режим без генерации клиента, скрипт по-прежнему принимает старый формат и тоже поддерживает необязательный `rate_mbit`:

```bash
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_PUBLIC_KEY> 10.80.0.2/32
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_PUBLIC_KEY> 10.80.0.2/32 "" 15
docker exec -it awg-core /opt/awg/scripts/add-peer.sh awg0 <CLIENT_PUBLIC_KEY> 10.80.0.2/32 "" 0
```

Удалить peer:

```bash
docker exec -it awg-core /opt/awg/scripts/remove-peer.sh awg0 <CLIENT_PUBLIC_KEY>
```

Список peer:

```bash
docker exec -it awg-core /opt/awg/scripts/list-peers.sh awg0
```

## Как создать клиента для проверки

1. Сгенерируйте ключи клиента:

```bash
awg genkey | tee client_private.key | awg pubkey > client_public.key
```

2. Возьмите `Server public key` из лога контейнера или из файла `./awg/data/server_public.key`.

3. Создайте клиентский конфиг, например `client.conf`:

```ini
[Interface]
PrivateKey = <CLIENT_PRIVATE_KEY>
Address = 10.80.0.2/32
DNS = 1.1.1.1

Jc = 7
Jmin = 50
Jmax = 1000
S1 = 68
S2 = 149
S3 = 32
S4 = 16
H1 = 471800590-471800690
H2 = 1246894907-1246895000
H3 = 923637689-923637690
H4 = 1769581055-1869581055

# i1-i5 опциональны. Если хотите проверить signature packets, задайте их и на клиенте.
I1 = QUIC:50:0a0b0c0d0e0f1011121314
I2 = DNS:50:000100000001000000000000

[Peer]
PublicKey = <SERVER_PUBLIC_KEY>
Endpoint = <SERVER_IP_OR_DOMAIN>:51823
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
```

4. Скрипт уже создаст peer на сервере и сохранит клиентские файлы:

- `./awg/data/clients/<CLIENT_NAME>.privatekey`
- `./awg/data/clients/<CLIENT_NAME>.publickey`
- `./awg/data/clients/<CLIENT_NAME>.conf`

## 🤖 Telegram Bot для управления VPN

Проект включает полнофункциональный Telegram бот для управления VPN конфигурациями пользователями.

### Возможности бота

- ✅ Создание VPN конфигов через Telegram
- ✅ QR-коды для мобильных приложений
- ✅ Экспорт в формате WireGuard и Amnezia
- ✅ Управление сроком действия конфигов
- ✅ Автоматические уведомления об истечении
- ✅ Администраторская панель для управления пользователями
- ✅ Ограничение пропускной способности per-peer
- ✅ Автоматическое восстановление ограничений при перезагрузке

### Быстрый старт с ботом

```bash
# 1. Скопировать шаблон конфигурации
cp .env.bot .env

# 2. Отредактировать .env с вашими данными
nano .env

# 3. Запустить с ботом
docker compose up -d

# 4. Проверить логи
docker compose logs -f bot
```

### Требования для бота

- Telegram Bot Token (от [@BotFather](https://t.me/BotFather))
- Ваш Telegram ID (от [@userinfobot](https://t.me/userinfobot))
- PostgreSQL 16 (включена в docker-compose)

### Команды бота

Пользователю:
- `/start` - Начало
- `/config` - Получить конфиг
- `/info` - Информация об аккаунте
- `/help` - Справка

Администратору (дополнительно):
- `/users` - Список пользователей
- `/stats` - Статистика

### Структура проекта бота

```
bot/
├── main.py                 # Входная точка
├── Dockerfile             # Контейнер бота
├── requirements.txt       # Зависимости
└── src/
    ├── config.py          # Конфигурация
    ├── scheduler.py       # Планировщик задач
    ├── database/          # БД модели
    ├── handlers/          # Обработчики команд
    └── services/          # Бизнес-логика
```

### Дополнительная документация

- 📖 [BOT_SETUP.md](docs/BOT_SETUP.md) - Подробная инструкция по настройке бота
- 🧪 [TESTING.md](docs/TESTING.md) - Тестирование и примеры использования
- 📋 [README_BOT.md](docs/README_BOT.md) - Полная документация по боту

### Стек технологий для бота

- Python 3.11 с aiogram 3.4.1
- PostgreSQL 16 для хранения данных
- SQLAlchemy 2.0 ORM
- APScheduler для автоматизации
- Docker для развертывания

## 🛠️ Rate Limiting (Ограничение скорости)

### Как работает

Скорость ограничивается двумя способами:

1. **Upload** (на интерфейсе awg0):
   - iptables MARK правила для каждого пира
   - tc (traffic control) с HTB дисциплиной

2. **Download** (на eth0):
   - iptables CONNMARK для обратного трафика
   - Восстанавливается при перезагрузке контейнера

### Восстановление при перезагрузке

Лимиты сохраняются в комментариях файлов конфига и автоматически восстанавливаются при старте контейнера через функцию `restore_peer_rate_limits()` в `entrypoint.sh`.

### Настройка лимитов через бота

```bash
# Переменная окружения
DEFAULT_RATE_LIMIT=15  # Mbit/s по умолчанию
```

При создании конфига через бота можно изменить лимит в коде:
```python
await PeerManager.add_peer(
    client_name=client_name,
    client_ip=next_ip,
    rate_limit=20  # Изменить здесь
)
```

## 📊 Архитектура системы

```
┌─────────────────────────────────────┐
│   Telegram Users                    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Telegram Bot (Python/aiogram)     │
│   - Handlers                        │
│   - Config generation               │
│   - Notifications                   │
└────┬────────────────────────────┬───┘
     │                            │
     ▼                            ▼
┌──────────────┐        ┌──────────────────┐
│  PostgreSQL  │        │   AmneziaWG VPN  │
│   (configs)  │        │   (awg-core)     │
│  (users)     │        │                  │
└──────────────┘        │  Rate limiting:  │
                        │  - iptables MARK │
                        │  - tc HTB        │
                        └──────────────────┘
```

## 🔐 Безопасность

- Все пароли хранятся в `.env` и никогда не коммитятся
- БД использует асинхронный драйвер (asyncpg) 
- WireGuard обеспечивает шифрование трафика
- Docker сети изолируют сервисы
- Логирование всех администраторских действий

## 🚀 Развертывание на продакшене

```bash
# 1. Клонировать репо
git clone <your-repo>
cd amnezia-wg-easy

# 2. Настроить переменные
cp .env.bot .env
# Отредактировать с боевыми данными

# 3. Запустить
docker compose -f docker-compose.yml up -d

# 4. Проверить
docker compose ps
docker compose logs
```

## 📞 Поддержка и вклад

Приветствуются Pull Requests и Issues!

Контакты:
- 📧 Email: support@example.com
- 🐛 Issues: GitHub Issues
- 💬 Telegram: [@supportbot](https://t.me/supportbot)

---

**Полнофункциональное решение для управления VPN через Telegram** 🚀

5. Импортируйте `client.conf` в AmneziaVPN или используйте его в любом AWG/WireGuard-клиенте, который поддерживает AmneziaWG 2.0.