# 🚀 QUICK START - Telegram Bot для AmneziaWG VPN

Полнофункциональное решение для управления VPN сервером через Telegram бота.

## ⚡ За 5 минут

### 1. Получить токены
- 🤖 Bot Token: Напишите [@BotFather](https://t.me/BotFather) и создайте нового бота
- 👤 Ваш ID: Напишите [@userinfobot](https://t.me/userinfobot)

### 2. Настроить
```bash
cp .env.bot .env
nano .env  # Вставить токен и ID
```

### 3. Запустить
```bash
docker compose up -d
```

### 4. Проверить
```bash
docker compose logs -f bot
```

Готово! Бот работает 🎉

---

## 📱 Использование в Telegram

1. Откройте чат с ботом
2. `/start` - начало работы
3. `📝 Получить конфиг` - создать VPN конфиг
4. Получите конфиг, QR-код, инструкции
5. Импортируйте в Amnezia/WireGuard
6. Подключитесь к VPN

---

## 📚 Документация

Для полной информации читайте:

| Документ | Описание |
|----------|---------|
| [BOT_SETUP.md](BOT_SETUP.md) | Подробная инструкция по настройке |
| [README_BOT.md](README_BOT.md) | Полная документация бота |
| [TESTING.md](TESTING.md) | Примеры и тестирование |
| [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) | Архитектура и дизайн |
| [FILE_STRUCTURE.md](FILE_STRUCTURE.md) | Структура файлов |
| [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) | Чек-лист реализации |

---

## 🎯 Основные возможности

✅ Создание VPN конфигов через Telegram  
✅ QR-коды для мобильных приложений  
✅ Управление сроком действия конфигов  
✅ Автоматические уведомления  
✅ Ограничение скорости per-peer  
✅ Администраторская панель  
✅ Полностью Docker-изирован  

---

## 🔧 Требования

- Docker & Docker Compose
- Telegram Bot Token
- Ваш Telegram ID
- Открытый порт 5066

---

## ❓ Troubleshooting

### Бот не отвечает
```bash
docker compose logs bot
# Проверить TELEGRAM_BOT_TOKEN в .env
```

### БД не подключается
```bash
docker compose logs postgres
```

### Полный ресет
```bash
docker compose down -v
docker compose up -d
```

---

## 📞 Помощь

- 🆘 Проверьте [BOT_SETUP.md](BOT_SETUP.md)
- 🧪 Примеры в [TESTING.md](TESTING.md)
- 📖 Полная инфо в [README_BOT.md](README_BOT.md)
- 🐛 Логи: `docker compose logs bot`

---

**Статус:** ✅ Production Ready  
**Версия:** 1.0.0  
**Дата:** 2024-04-22
