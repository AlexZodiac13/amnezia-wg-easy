import logging
import asyncio
from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramNetworkError

from src.services.database_service import DatabaseService
from src.services.peer_manager import PeerManager
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
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="📋 Лист")],
            [KeyboardButton(text="📝 Получить конфиг с именем")],
            [KeyboardButton(text="📂 Мои конфиги")],
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
        if user is None:
            logger.error("get_or_create_user returned None for telegram_id %s", telegram_id)
            user = await DatabaseService.create_user(session, telegram_id, username)

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
            if user.is_admin:
                expiration_label = "Неограничено"
                expires_at_label = "Неограничено"
            else:
                expiration_label = f"{config.days_until_expiration()} дней"
                expires_at_label = config.expires_at.strftime('%d.%m.%Y')

            info_text += f"""
- Имя: `{config.client_name}`
- IP адрес: `{config.client_ip}`
- Срок действия: `{expiration_label}`
- Истекает: `{expires_at_label}`
"""
        else:
            info_text += "\nНет активной конфигурации. Используйте кнопку '📝 Получить конфиг'"
        
        await safe_answer(message, info_text, parse_mode="Markdown")

admin_named_config_pending: set[int] = set()

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

@router.message(F.text == "📝 Получить конфиг с именем")
async def request_named_config(message: types.Message):
    telegram_id = message.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return

    admin_named_config_pending.add(telegram_id)
    await safe_answer(
        message,
        "✍️ Введите имя конфига. Разрешены буквы, цифры, дефисы и подчеркивания."
    )

@router.message(lambda message: message.from_user.id in admin_named_config_pending)
async def handle_admin_named_config(message: types.Message):
    telegram_id = message.from_user.id
    if telegram_id not in admin_named_config_pending:
        return

    if message.text == "📝 Получить конфиг" or message.text.startswith("/"):
        return

    desired_name = message.text.strip()

    from re import sub
    safe_name = sub(r'[^A-Za-z0-9_.-]+', '_', desired_name).strip('_-.')
    if not safe_name:
        await safe_answer(message, "❌ Некорректное имя. Попробуйте ещё раз.")
        return

    admin_named_config_pending.discard(telegram_id)
    status_message = await message.answer("⏳ Создаю конфиг... Это может занять несколько секунд...")
    if status_message:
        await create_and_send_config_for_user(telegram_id, status_message, client_name=safe_name)

@router.message(Command("config"))
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
        
        if active_config and not active_config.is_expired() and not user.is_admin:
            # Если есть активный, предложить новый только обычному пользователю
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

@router.message(F.text == "📂 Мои конфиги")
async def show_admin_configs(message: types.Message):
    """Показать все конфиги администратора"""
    telegram_id = message.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return

        configs = await DatabaseService.get_user_configs(session, user.id)
        if not configs:
            await safe_answer(message, "📂 У вас пока нет конфигов")
            return

        text_lines = ["📂 **Ваши конфиги:**\n", "Нажмите кнопку рядом с нужным конфигом:\n"]
        buttons = []
        for idx, cfg in enumerate(configs, start=1):
            status = "Активный" if cfg.is_active and not cfg.is_expired() else "Неактивный"
            text_lines.append(f"{idx}. `{cfg.client_name}` | {cfg.client_ip} | {status} | {cfg.rate_limit} Mbit/s")
            buttons.append([
                InlineKeyboardButton(
                    text=f"📄 Получить {idx}",
                    callback_data=f"admin_config:{cfg.config_id}"
                ),
                InlineKeyboardButton(
                    text=f"❌ Удалить {idx}",
                    callback_data=f"delete_admin_config:{cfg.config_id}"
                )
            ])

        buttons.append([
            InlineKeyboardButton(text="Обновить список", callback_data="show_admin_configs")]
        )

        await safe_answer(
            message,
            "\n".join(text_lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

@router.callback_query(F.data == "show_admin_configs")
async def handle_show_admin_configs(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    await query.answer()
    await show_admin_configs(query.message)

@router.callback_query(F.data.startswith("delete_admin_config:"))
async def delete_admin_config(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    config_id = query.data.split(":", 1)[1]

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user or not user.is_admin:
            await query.answer("❌ У вас нет прав для этой операции", show_alert=True)
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден", show_alert=True)
            return

        remove_result = await PeerManager.remove_peer(config.client_name, config.client_public_key)
        if not remove_result.get("success", False):
            error_text = remove_result.get("error", "Не удалось удалить пир из AWG")
            logger.warning("Failed to remove peer %s: %s", config.client_name, error_text)
            await query.answer(f"❌ Ошибка: {error_text}", show_alert=True)
            return

        await DatabaseService.delete_config(session, config_id)
        await query.answer("✅ Конфиг удалён")
        await show_admin_configs(query.message)

@router.message(Command("help"))
async def help_command(message: types.Message):
    """Команда /help"""
    help_text = """
🆘 **Справка по Amnezia VPN Bot**

Доступные команды:
- /start — начать работу и показать меню
- /config — получить новый VPN конфиг
- /info — информация о текущем аккаунте
- /help — справка

Также можете использовать кнопки:
- 📝 Получить конфиг
- ℹ️ Информация
- 🆘 Поддержка
"""
    await safe_answer(message, help_text, parse_mode="Markdown")

@router.message(F.text == "👥 Пользователи")
async def user_count(message: types.Message):
    """Пользователи (только для админа)"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return
        
        count = await DatabaseService.get_user_count(session)
        await safe_answer(message, f"👥 **Количество активных пользователей:** `{count}`", parse_mode="Markdown")

@router.message(F.text == "📋 Лист")
async def user_list(message: types.Message):
    """Лист пользователей (только для админа)"""
    telegram_id = message.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user or not user.is_admin:
            await safe_answer(message, "❌ У вас нет прав для этой команды")
            return
        
        users = await DatabaseService.get_all_users(session)
        
        if not users:
            await safe_answer(message, "📋 Лист пуст")
            return
        
        text = "📋 **Список всех пользователей:**\n\n"
        for idx, u in enumerate(users, 1):
            text += f"{idx}. ID: `{u.telegram_id}`, Username: `{u.username}`, "
            text += f"Статус: {'👑 Админ' if u.is_admin else '👤 Пользователь'}\n"
        
        await safe_answer(message, text, parse_mode="Markdown")
