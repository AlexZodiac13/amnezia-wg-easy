import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, Update
from aiogram.types import User as TGUser
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Filter

from src.config import Config
from src.database.db import init_db, close_db
from src.database import db
from src.handlers import commands, config_handlers
from src.scheduler import NotificationScheduler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=Config.TELEGRAM_BOT_TOKEN, parse_mode="Markdown")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Добавление обработчиков
dp.include_router(commands.router)
dp.include_router(config_handlers.router)

# Планировщик
scheduler = None

class SessionMiddleware(Filter):
    """Middleware для передачи сессии БД"""
    async def __call__(self, update: Update) -> bool:
        return True

async def set_commands():
    """Установить команды бота"""
    commands_list = [
        BotCommand(command="start", description="Начать работу"),
        BotCommand(command="config", description="Получить конфиг"),
        BotCommand(command="info", description="Информация о аккаунте"),
        BotCommand(command="help", description="Справка"),
    ]
    
    await bot.set_my_commands(commands_list)
    logger.info("Bot commands set")

async def process_update(update: Update) -> None:
    """Обработчик обновлений с передачей сессии"""
    async with db.async_session() as session:
        # Передаём сессию в контекст
        update.session = session
        await dp.feed_update(bot, update)

async def main():
    """Главная функция"""
    global scheduler
    
    try:
        # Инициализация БД
        logger.info("Initializing database...")
        await init_db()
        
        logger.info("Database initialized successfully")
        
        # Установка команд
        await set_commands()
        
        # Запуск планировщика
        logger.info("Starting notification scheduler...")
        scheduler = NotificationScheduler(bot)
        await scheduler.start(db.async_session)
        
        # Запуск диспетчера с middleware для сессии
        logger.info("Starting bot polling...")
        
        # Получить обновления и обрабатывать их
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            skip_updates=False
        )
        
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
    
    finally:
        # Закрытие ресурсов
        logger.info("Shutting down...")
        if scheduler:
            await scheduler.stop()
        await close_db()
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted")
        exit(0)
