# Bot Setup Guide

## Prerequisites

- Docker & Docker Compose
- Telegram Bot Token (get from @BotFather on Telegram)
- Your Telegram ID (get from @userinfobot on Telegram)

## Setup Instructions

### 1. Configure Environment Variables

Copy `.env.bot` to `.env`:
```bash
cp .env.bot .env
```

Edit `.env` and fill in your values:
```env
TELEGRAM_BOT_TOKEN=your_token_from_botfather
ADMIN_TELEGRAM_ID=your_telegram_id
POSTGRES_PASSWORD=your_secure_password
```

### 2. Build and Run

```bash
docker compose up -d
```

This will:
- Start the AmneziaWG VPN service
- Start PostgreSQL database
- Build and start the Telegram bot

### 3. Verify Bot is Running

Check logs:
```bash
docker compose logs -f bot
```

You should see:
```
Bot commands set
Initializing database...
Starting notification scheduler...
Starting bot polling...
```

### 4. Test the Bot

Open Telegram and start a chat with your bot:
- Type `/start` to begin
- Click "📝 Получить конфиг" to create a VPN config
- Check `/info` to see your account details

## Bot Commands

### For Regular Users:
- `/start` - Start the bot
- `/config` - Create/view VPN configuration
- `/info` - View account information
- `/help` - Show help message

### For Admins:
- All user commands above
- `/users` - List all users
- `/stats` - View user statistics
- `/delete_user <telegram_id>` - Delete a user and their configs

## Features

### 🔐 VPN Configuration Management
- Automatic peer creation in AmneziaWG
- QR-code generation for mobile apps
- WireGuard config file export
- Amnezia app backup JSON format

### ⏰ Expiration Management
- 30-day default expiration (configurable)
- Automatic 3-day pre-expiry notifications
- Auto-deletion of expired configs
- Config renewal with new keys

### 📊 Admin Dashboard
- User statistics
- User list with deletion
- Active config count

### 🔄 Rate Limiting
- Per-peer bandwidth limits (default: 15 Mbit/s)
- Persistent across VPN restarts
- Configurable via bot settings

## Troubleshooting

### Bot not responding
```bash
docker compose logs bot
```

### Database connection issues
```bash
docker compose logs postgres
```

### VPN interface errors
```bash
docker compose logs awg
```

### Reset Everything
```bash
docker compose down -v
docker compose up -d
```

## Database Reset

To clear all users and configs:
```bash
docker compose exec postgres psql -U bot_user -d amnezia_bot -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

## Rate Limiting Configuration

Edit environment variables to change rate limits:
- `DEFAULT_RATE_LIMIT` - Default bandwidth per user (Mbit/s)
- `EXPIRATION_DAYS` - Config validity period (days)
- `NOTIFICATION_DAYS` - Pre-expiry notification time (days)

## Architecture

```
User (Telegram)
    ↓
Bot (Python + Aiogram)
    ↓
PostgreSQL (Config storage)
    ↓
AmneziaWG (VPN service)
```

## Security Notes

- Change default PostgreSQL password in `.env`
- Use strong bot token
- Only share bot with trusted users
- Monitor logs for unauthorized access attempts
- Keep Docker images updated

## Support

For issues or feature requests, check:
- Bot logs: `docker compose logs bot`
- Database: Connect via psql
- VPN: Check AWG container status
