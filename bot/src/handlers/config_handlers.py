import ipaddress
import logging
import os
import re
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
import uuid
from datetime import datetime, timedelta

from src.services.database_service import DatabaseService
from src.services.peer_manager import PeerManager
from src.services.config_manager import ConfigManager
from src.database import db
from src.config import Config

logger = logging.getLogger(__name__)
router = Router()


async def get_next_available_ip(session) -> str:
    """Найти следующий свободный IP в подсети из AWG_SUBNET."""
    used_ips = await DatabaseService.get_active_client_ips(session)
    subnet = ipaddress.ip_network(Config.AWG_SUBNET, strict=False)
    server_ip = ipaddress.ip_address(Config.AWG_SUBNET.split('/')[0])

    used_addresses = set()
    for ip in used_ips:
        ip = ip.strip()
        if not ip:
            continue
        try:
            used_addresses.add(ipaddress.ip_address(ip))
        except ValueError:
            # Возможно, в БД уже хранится CIDR-подсеть, игнорируем
            if '/' in ip:
                try:
                    used_addresses.add(ipaddress.ip_address(ip.split('/')[0]))
                except ValueError:
                    continue
            continue

    for candidate in subnet.hosts():
        if candidate == server_ip:
            continue
        if candidate not in used_addresses:
            return str(candidate)

    raise RuntimeError(f"Нет доступных IP-адресов в подсети {subnet}")


def build_config_artifact_keyboard(config_id: str | None = None) -> InlineKeyboardMarkup:
    # Основное меню: только выбор устройства (телефон/ПК), инструкции будут после бекапа
    if config_id:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Настройки телефона", callback_data=f"setup_phone:{config_id}")],
            [InlineKeyboardButton(text="💻 Настройки ПК", callback_data=f"setup_pc:{config_id}")],
            [InlineKeyboardButton(text="⚙️ Для продвинутых пользователей", callback_data=f"adv:{config_id}")],
        ])

    # Фолбэк без config_id
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Настройки телефона", callback_data="setup_phone")],
        [InlineKeyboardButton(text="💻 Настройки ПК", callback_data="setup_pc")],
        [InlineKeyboardButton(text="⚙️ Для продвинутых пользователей", callback_data="adv")],
    ])


def normalize_client_name(raw_name: str) -> str:
    clean_name = re.sub(r'[^A-Za-z0-9_.-]+', '_', raw_name.strip())
    clean_name = clean_name.strip('_.-')
    return clean_name[:50] if clean_name else ''

async def create_and_send_config_for_user(
    telegram_id: int,
    target_message: types.Message,
    client_name: str | None = None
) -> bool:
    """Создать новый конфиг для пользователя и отправить все артефакты в чат."""
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)

        if not user:
            await target_message.edit_text("❌ Ошибка: пользователь не найден")
            return False

        try:
            # Для обычного пользователя деактивируем предыдущий активный конфиг.
            # Администратор может иметь несколько активных конфигов.
            if not user.is_admin:
                old_config = await DatabaseService.get_active_config(session, user.id)
                if old_config:
                    await DatabaseService.deactivate_config(session, old_config.config_id)
                    # Удалить пира из WireGuard
                    await PeerManager.remove_peer(old_config.client_name, old_config.client_public_key)

            # Найти следующий свободный IP в /16
            next_ip = await get_next_available_ip(session)

            # Генерировать имя клиента или использовать имя администратора
            if client_name:
                client_name = normalize_client_name(client_name)
                if not client_name:
                    client_name = f"tg_{telegram_id}_{datetime.utcnow().timestamp():.0f}"
            else:
                client_name = f"tg_{telegram_id}_{datetime.utcnow().timestamp():.0f}"

            # Если такой файл уже существует, добавить суффикс
            candidate_name = client_name
            suffix = 1
            while os.path.exists(os.path.join(Config.CONFIGS_DIR, f"{candidate_name}.conf")):
                candidate_name = f"{client_name}_{suffix}"
                suffix += 1
            client_name = candidate_name

            admin_rate_limit = Config.ADMIN_RATE_LIMIT if user.is_admin else Config.DEFAULT_RATE_LIMIT
            admin_expiration_days = Config.ADMIN_EXPIRATION_DAYS if user.is_admin else Config.EXPIRATION_DAYS

            # Добавить пира
            peer_result = await PeerManager.add_peer(
                client_name=client_name,
                client_ip=next_ip,
                rate_limit=admin_rate_limit
            )

            if not peer_result["success"]:
                await target_message.edit_text(f"❌ Ошибка при создании конфига:\n{peer_result['error']}")
                return False

            config_content = peer_result["config"]
            config_id = str(uuid.uuid4())

            # Парсить конфиг и извлечь ключи
            parsed = ConfigManager.parse_wg_config(config_content)
            client_private_key = parsed.get("interface", {}).get("PrivateKey", "")
            client_preshared_key = parsed.get("peer", {}).get("PresharedKey", "")

            # Вычислить публичный ключ
            import subprocess
            result = subprocess.run(
                f"echo {client_private_key} | wg pubkey",
                shell=True,
                capture_output=True,
                text=True
            )
            client_public_key = result.stdout.strip()

            # Сохранить в БД
            await DatabaseService.create_config(
                session=session,
                user_id=user.id,
                config_id=config_id,
                client_name=client_name,
                client_private_key=client_private_key,
                client_public_key=client_public_key,
                client_preshared_key=client_preshared_key,
                client_ip=next_ip,
                wg_config_content=config_content,
                rate_limit=admin_rate_limit,
                expires_at=datetime.utcnow() + timedelta(days=admin_expiration_days)
            )

            # Отправить результат с кнопками для выбора артефакта
            expiration_label = "Неограничено" if user.is_admin else f"{Config.EXPIRATION_DAYS} дней"
            expires_at_label = "Неограничено" if user.is_admin else f"{(datetime.utcnow() + timedelta(days=Config.EXPIRATION_DAYS)).strftime('%d.%m.%Y') }"
            text = f"""
✅ **Конфиг успешно создан!**

📝 **Информация о конфиге:**
- Имя: `{client_name}`
- IP адрес: `{next_ip}`
- Срок действия: `{expiration_label}`
- Истекает: `{expires_at_label}`

Выберите, где будете настраивать VPN: телефон или ПК. После получения бекапа я предложу показать инструкцию для выбранного устройства.
            """

            await target_message.edit_text(
                text,
                parse_mode="Markdown",
                reply_markup=build_config_artifact_keyboard(config_id)
            )
            return True

        except Exception as e:
            logger.error(f"Exception in create_and_send_config_for_user: {str(e)}")
            await target_message.edit_text(f"❌ Ошибка при создании конфига:\n{str(e)}")
            return False

@router.callback_query(F.data == "create_new_config")
async def create_new_config(query: types.CallbackQuery):
    """Создать новый конфиг"""
    telegram_id = query.from_user.id

    await query.message.edit_text("⏳ Создаю конфиг... Это может занять несколько секунд...")
    await create_and_send_config_for_user(telegram_id, query.message)
    await query.answer()

@router.callback_query(F.data == "show_current_config")
async def show_current_config(query: types.CallbackQuery):
    """Показать текущий конфиг"""
    telegram_id = query.from_user.id
    
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return
        
        config = await DatabaseService.get_active_config(session, user.id)
        
        if not config:
            await query.message.edit_text("❌ У вас нет активного конфига")
            await query.answer()
            return
        
        if user.is_admin:
            expiration_label = "Неограничено"
            expires_at_label = "Неограничено"
        else:
            expiration_label = f"{config.days_until_expiration()} дней"
            expires_at_label = config.expires_at.strftime('%d.%m.%Y')

        text = f"""
📋 **Ваш текущий конфиг:**

- Имя: `{config.client_name}`
- IP адрес: `{config.client_ip}`
- Срок действия: `{expiration_label}`
- Истекает: `{expires_at_label}`
        """
        
        await query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_config_artifact_keyboard(config.config_id)
        )
        await query.answer()


@router.callback_query(F.data.startswith("admin_config:"))
async def show_admin_config(query: types.CallbackQuery):
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

        status = "Активный" if config.is_active and not config.is_expired() else "Неактивный"
        expiration_label = "Неограничено" if user.is_admin else f"{config.days_until_expiration()} дней"
        expires_at_label = "Неограничено" if user.is_admin else config.expires_at.strftime('%d.%m.%Y')

        text = f"""
📋 **Информация о конфигах:**

- Имя: `{config.client_name}`
- IP адрес: `{config.client_ip}`
- Статус: `{status}`
- Срок действия: `{expiration_label}`
- Истекает: `{expires_at_label}`
"""

        await query.answer("🔎 Открываю конфиг...")
        await query.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_config_artifact_keyboard(config_id)
        )

@router.callback_query(F.data.startswith("adv:"))
async def show_advanced_menu(query: types.CallbackQuery):
    """Показать подменю «Для продвинутых пользователей» с текстом/файлом конфига."""
    config_id = query.data.split(":", 1)[1]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Текст конфига", callback_data=f"sct:{config_id}")],
        [InlineKeyboardButton(text="📎 Файл конфига", callback_data=f"scf:{config_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_art:{config_id}")],
    ])
    await query.message.edit_text(
        "⚙️ Для продвинутых пользователей:\nВыберите формат получения конфига:",
        reply_markup=keyboard
    )
    await query.answer()

@router.callback_query(F.data.startswith("back_art:"))
async def back_to_artifacts(query: types.CallbackQuery):
    """Вернуться к основным артефактам (настройки телефона/ПК)."""
    config_id = query.data.split(":", 1)[1]
    await query.message.edit_text(
        "Выберите действие:",
        reply_markup=build_config_artifact_keyboard(config_id)
    )
    await query.answer()


@router.callback_query(F.data.startswith("sct:"))
async def send_config_text(query: types.CallbackQuery):
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        await query.message.answer("```\n" + config.wg_config_content + "\n```", parse_mode="Markdown")
        await query.answer("✅ Текст конфига отправлен")


@router.callback_query(F.data.startswith("scf:"))
async def send_config_file(query: types.CallbackQuery):
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        config_file = types.BufferedInputFile(
            file=config.wg_config_content.encode(),
            filename=f"{config.client_name}.conf"
        )
        await query.message.answer_document(
            document=config_file,
            caption="📄 Файл конфига Amnezia WireGuard"
        )
        await query.answer("✅ Файл конфига отправлен")

@router.callback_query(F.data.startswith("setup_pc:"))
async def setup_pc_and_offer_instruction(query: types.CallbackQuery):
    """Отправить бекап для ПК и предложить кнопку с инструкцией для ПК."""
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        amnezia_backup = ConfigManager.generate_pc_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_pc_backup.backup"
        )

        await query.message.answer_document(
            document=backup_file,
            caption="💻 Персональный бекап для ПК"
        )

        # Предложить показать инструкцию
        instruct_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💻 Показать инструкцию для ПК", callback_data=f"pc:{config_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_art:{config_id}")],
        ])
        await query.message.answer(
            "Хотите получить инструкцию по настройке ПК?",
            reply_markup=instruct_kb
        )
    await query.answer("✅ Бекап для ПК отправлен")

@router.callback_query(F.data.startswith("setup_phone:"))
async def setup_phone_and_offer_instruction(query: types.CallbackQuery):
    """Отправить бекап для телефона и предложить кнопку с инструкцией для телефона."""
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        amnezia_backup = ConfigManager.generate_amnezia_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_backup.backup"
        )
        await query.message.answer_document(
            document=backup_file,
            caption="📱 Бекап для приложения Amnezia (телефон)"
        )

        # Предложить показать инструкцию
        instruct_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Показать инструкцию для телефона", callback_data=f"sp:{config_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_art:{config_id}")],
        ])
        await query.message.answer(
            "Хотите получить инструкцию по настройке телефона?",
            reply_markup=instruct_kb
        )
    await query.answer("✅ Бекап для телефона отправлен")

@router.callback_query(F.data == "setup_pc")
async def setup_pc_default(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return
        config = await DatabaseService.get_active_config(session, user.id)
        if not config:
            await query.answer("❌ У вас нет активного конфига")
            return

        # Переиспользуем логику с config_id
        class Q:
            data = f"setup_pc:{config.config_id}"
            from_user = query.from_user
            message = query.message
            def __getattr__(self, name):
                return getattr(query, name)
        await setup_pc_and_offer_instruction(Q)  # type: ignore

@router.callback_query(F.data == "setup_phone")
async def setup_phone_default(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return
        config = await DatabaseService.get_active_config(session, user.id)
        if not config:
            await query.answer("❌ У вас нет активного конфига")
            return

        class Q:
            data = f"setup_phone:{config.config_id}"
            from_user = query.from_user
            message = query.message
            def __getattr__(self, name):
                return getattr(query, name)
        await setup_phone_and_offer_instruction(Q)  # type: ignore

@router.callback_query(F.data == "adv")
async def show_advanced_menu_default(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return
        config = await DatabaseService.get_active_config(session, user.id)
        if not config:
            await query.answer("❌ У вас нет активного конфига")
            return

        class Q:
            data = f"adv:{config.config_id}"
            from_user = query.from_user
            message = query.message
            def __getattr__(self, name):
                return getattr(query, name)
        await show_advanced_menu(Q)  # type: ignore


@router.callback_query(F.data.startswith("pc_backup:"))
async def send_pc_backup(query: types.CallbackQuery):
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        amnezia_backup = ConfigManager.generate_pc_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_pc_backup.backup"
        )

        await query.message.answer_document(
            document=backup_file,
            caption="💻 Персональный бекап для ПК"
        )
        await query.answer("✅ Бекап для ПК отправлен")


@router.callback_query(F.data == "send_pc_backup")
async def send_pc_backup_default(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_active_config(session, user.id)
        if not config:
            await query.answer("❌ У вас нет активного конфига")
            return

        amnezia_backup = ConfigManager.generate_pc_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_pc_backup.backup"
        )

        await query.message.answer_document(
            document=backup_file,
            caption="💻 Персональный бекап для ПК"
        )
    await query.answer("✅ Бекап для ПК отправлен")


@router.callback_query(F.data.startswith("sab:"))
async def send_amnezia_backup(query: types.CallbackQuery):
    config_id = query.data.split(":", 1)[1]
    telegram_id = query.from_user.id

    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_config_by_id(session, config_id)
        if not config or config.user_id != user.id:
            await query.answer("❌ Конфиг не найден")
            return

        amnezia_backup = ConfigManager.generate_amnezia_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_backup.backup"
        )
        await query.message.answer_document(
            document=backup_file,
            caption="📦 JSON бекап конфига"
        )
        await query.answer("✅ JSON бекап отправлен")


@router.callback_query(F.data == "send_amnezia_backup")
async def send_amnezia_backup(query: types.CallbackQuery):
    telegram_id = query.from_user.id
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)
        if not user:
            await query.answer("❌ Ошибка: пользователь не найден")
            return

        config = await DatabaseService.get_active_config(session, user.id)
        if not config:
            await query.answer("❌ У вас нет активного конфига")
            return

        amnezia_backup = ConfigManager.generate_amnezia_backup_full(
            config.wg_config_content,
            config.client_name
        )
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_backup.backup"
        )
        await query.message.answer_document(
            document=backup_file,
            caption="💾 Бекап для приложения Amnezia"
        )
        await query.answer("✅ Бекап отправлен")


@router.callback_query(F.data == "send_setup_instruction_phone")
async def send_setup_instruction_phone(query: types.CallbackQuery):
    instruction_text = ConfigManager.create_setup_instruction("phone")
    
    # Отправить текст инструкции
    await query.message.answer(instruction_text, parse_mode="Markdown")
    
    await query.answer("✅ Инструкция для телефона отправлена")

@router.callback_query(F.data.startswith("sp:"))
async def send_setup_instruction_phone_with_config(query: types.CallbackQuery):
    instruction_text = ConfigManager.create_setup_instruction("phone")
    await query.message.answer(instruction_text, parse_mode="Markdown")
    await query.answer("✅ Инструкция для телефона отправлена")

@router.callback_query(F.data == "send_setup_instruction_pc")
async def send_setup_instruction_pc(query: types.CallbackQuery):
    instruction_text = ConfigManager.create_setup_instruction("pc")
    await query.message.answer(instruction_text, parse_mode="Markdown")
    await query.answer("✅ Инструкция для ПК отправлена")

@router.callback_query(F.data.startswith("pc:"))
async def send_setup_instruction_pc_with_config(query: types.CallbackQuery):
    instruction_text = ConfigManager.create_setup_instruction("pc")
    await query.message.answer(instruction_text, parse_mode="Markdown")
    await query.answer("✅ Инструкция для ПК отправлена")
