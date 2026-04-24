import logging
import asyncio
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramNetworkError

from src.services.database_service import DatabaseService
from src.database import db
from src.config import Config
from src.handlers.config_handlers import create_and_send_config_for_user

logger = logging.getLogger(__name__)
router = Router()


async def safe_answer(message: types.Message, text: str, **kwargs):
    """Send message with retries on transient Telegram network errors."""
    retries = 3
    for attempt in range(retries):
        try:
            return await message.answer(text, **kwargs)
        except TelegramNetworkError as exc:
            if attempt == retries - 1:
                logger.error(f"Telegram send failed after retries: {exc}")
                return None
            await asyncio.sleep(attempt + 1)

# Клавиатура для обычного пользователя
def get_user_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Получить конфиг")],
            [KeyboardButton(text="ℹ️ Информация")],
            [KeyboardButton(text="🆘 Поддержка")],
        ],
        resize_keyboard=True
    )

# Клавиатура для админа
def get_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Количество пользователей"), KeyboardButton(text="📋 Список пользователей")],
            [KeyboardButton(text="📝 Получить конфиг")],
            [KeyboardButton(text="ℹ️ Информация")],
        ],
        resize_keyboard=True
    )

@router.message(CommandStart())
async def start(message: types.Message):
    """Команда /start"""
    telegram_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    async with db.async_session() as session:
        # Получить или создать пользователя
        user = await DatabaseService.get_or_create_user(session, telegram_id, username)
        
        welcome_text = f"""
🔐 Добро пожаловать в Amnezia VPN Bot!

Привет, {username}! 👋

Я помогу вам управлять VPN конфигурациями.

Ваш Telegram ID: `{telegram_id}`
{"(Вы администратор)" if user.is_admin else ""}

Выберите действие из меню ниже 👇
        """
        
        keyboard = get_admin_keyboard() if user.is_admin else get_user_keyboard()
        await safe_answer(message, welcome_text, reply_markup=keyboard)

@router.message(Command("info"))
@router.message(F.text == "ℹ️ Информация")
async def info(message: types.Message):
    """Информация о боте"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        config = await DatabaseService.get_active_config(session, user.id) if user else None
        
        info_text = f"""
ℹ️ **Информация о вашем аккаунте**

Telegram ID: `{telegram_id}`
Статус: {"👑 Администратор" if user and user.is_admin else "👤 Пользователь"}

**Текущая конфигурация:**
"""
        
        if config:
            days_left = config.days_until_expiration()
            info_text += f"""
- Имя: `{config.client_name}`
- IP адрес: `{config.client_ip}`
- Скорость: `{config.rate_limit} Mbit/s`
- Срок действия: `{days_left} дней`
- Истекает: `{config.expires_at.strftime('%d.%m.%Y')}`
"""
        else:
            info_text += "\nНет активной конфигурации. Используйте кнопку '📝 Получить конфиг'"
        
        await safe_answer(message, info_text, parse_mode="Markdown")

@router.message(F.text == "🆘 Поддержка")
async def support(message: types.Message):
    """Помощь и поддержка"""
    support_text = """
🆘 **Служба поддержки**

Если у вас возникли проблемы с VPN:

1. Убедитесь, что конфиг загружен правильно
2. Проверьте интернет-соединение
3. Переподключитесь к VPN
4. Обновите приложение Amnezia

    """
    await safe_answer(message, support_text, parse_mode="Markdown")

@router.message(F.text == "📝 Получить конфиг")
async def get_config(message: types.Message):
    """Получить конфиг"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user:
            user = await DatabaseService.get_or_create_user(session, telegram_id)
        
        # Проверить, есть ли уже активный конфиг
        active_config = await DatabaseService.get_active_config(session, user.id)
        
        if active_config and not active_config.is_expired():
            # Если есть активный, предложить новый
            await safe_answer(
                message,
                "📋 У вас уже есть активный конфиг. Создать новый?",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Да, создать новый", callback_data="create_new_config")],
                        [InlineKeyboardButton(text="❌ Нет, показать текущий", callback_data="show_current_config")],
                    ]
                )
            )
        else:
            # Создать новый конфиг
            status_message = await safe_answer(message, "⏳ Создаю конфиг... Это может занять несколько секунд...")
            if status_message:
                await create_and_send_config_for_user(telegram_id, status_message)

@router.message(F.text == "👥 Количество пользователей")
async def user_count(message: types.Message):
    """Количество пользователей (только для админа)"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return
        
        count = await DatabaseService.get_user_count(session)
        await safe_answer(message, f"👥 **Количество активных пользователей:** `{count}`", parse_mode="Markdown")

@router.message(F.text == "📋 Список пользователей")
async def user_list(message: types.Message):
    """Список пользователей (только для админа)"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return
        
        users = await DatabaseService.get_all_users(session)
        
        if not users:
            await safe_answer(message, "📋 Список пользователей пуст")
            return
        
        text = "📋 **Список всех пользователей:**\n\n"
        for idx, u in enumerate(users, 1):
            text += f"{idx}. ID: `{u.telegram_id}`, Username: `{u.username}`, "
            text += f"Статус: {'👑 Админ' if u.is_admin else '👤 Пользователь'}\n"
        
        await safe_answer(message, text, parse_mode="Markdown")
