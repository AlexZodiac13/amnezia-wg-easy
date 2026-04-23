import ipaddress
import logging
from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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


async def create_and_send_config_for_user(telegram_id: int, target_message: types.Message) -> bool:
    """Создать новый конфиг для пользователя и отправить все артефакты в чат."""
    async with db.async_session() as session:
        user = await DatabaseService.get_user(session, telegram_id)

        if not user:
            await target_message.edit_text("❌ Ошибка: пользователь не найден")
            return False

        try:
            # Деактивировать старый конфиг
            old_config = await DatabaseService.get_active_config(session, user.id)
            if old_config:
                await DatabaseService.deactivate_config(session, old_config.config_id)
                # Удалить пира из WireGuard
                await PeerManager.remove_peer(old_config.client_name, old_config.client_public_key)

            # Найти следующий свободный IP в /16
            next_ip = await get_next_available_ip(session)

            # Генерировать имя клиента
            client_name = f"tg_{telegram_id}_{datetime.utcnow().timestamp():.0f}"

            # Добавить пира
            peer_result = await PeerManager.add_peer(
                client_name=client_name,
                client_ip=next_ip,
                rate_limit=Config.DEFAULT_RATE_LIMIT
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
                rate_limit=Config.DEFAULT_RATE_LIMIT
            )

            # Генерировать QR код
            qr_bytes = ConfigManager.generate_qr_code(config_content)

            # Генерировать бекап для Amnezia
            amnezia_backup = ConfigManager.generate_amnezia_backup(config_content, client_name)

            # Отправить результат
            text = f"""
✅ **Конфиг успешно создан!**

📝 **Информация о конфиге:**
- Имя: `{client_name}`
- IP адрес: `{next_ip}`
- Скорость: `{Config.DEFAULT_RATE_LIMIT} Mbit/s`
- Срок действия: `30 дней`
- Истекает: `{(datetime.utcnow() + timedelta(days=30)).strftime('%d.%m.%Y')}`

Ниже вы получите:
1. Текст конфига
2. QR-код
3. Файл конфига
4. JSON бекап для Amnezia
5. Инструкция по настройке
            """

            await target_message.edit_text(text, parse_mode="Markdown")

            # Отправить текст конфига
            await target_message.answer(f"```\n{config_content}\n```", parse_mode="Markdown")

            # Отправить QR-код
            if qr_bytes:
                await target_message.answer_photo(
                    photo=types.BufferedInputFile(file=qr_bytes, filename="qr_code.png"),
                    caption="📱 QR-код для сканирования"
                )

            # Отправить файл конфига
            config_file = types.BufferedInputFile(
                file=config_content.encode(),
                filename=f"{client_name}.conf"
            )
            await target_message.answer_document(
                document=config_file,
                caption="📄 Файл конфига WireGuard"
            )

            # Отправить JSON бекап
            import json
            backup_json = json.dumps(amnezia_backup, indent=2)
            backup_file = types.BufferedInputFile(
                file=backup_json.encode(),
                filename=f"{client_name}_amnezia_backup.json"
            )
            await target_message.answer_document(
                document=backup_file,
                caption="💾 Бекап для приложения Amnezia"
            )

            # Отправить инструкцию
            instruction = ConfigManager.create_setup_instruction()
            await target_message.answer(instruction, parse_mode="Markdown")

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
        
        # Генерировать QR код
        qr_bytes = ConfigManager.generate_qr_code(config.wg_config_content)
        
        # Генерировать бекап для Amnezia
        amnezia_backup = ConfigManager.generate_amnezia_backup(
            config.wg_config_content,
            config.client_name
        )
        
        text = f"""
📋 **Ваш текущий конфиг:**

- Имя: `{config.client_name}`
- IP адрес: `{config.client_ip}`
- Скорость: `{config.rate_limit} Mbit/s`
- Срок действия: `{config.days_until_expiration()} дней`
- Истекает: `{config.expires_at.strftime('%d.%m.%Y')}`
        """
        
        await query.message.edit_text(text, parse_mode="Markdown")
        
        # Отправить текст конфига
        await query.message.answer(f"```\n{config.wg_config_content}\n```", parse_mode="Markdown")
        
        # Отправить QR-код
        if qr_bytes:
            await query.message.answer_photo(
                photo=types.BufferedInputFile(file=qr_bytes, filename="qr_code.png"),
                caption="📱 QR-код для сканирования"
            )
        
        # Отправить файл конфига
        config_file = types.BufferedInputFile(
            file=config.wg_config_content.encode(),
            filename=f"{config.client_name}.conf"
        )
        await query.message.answer_document(
            document=config_file,
            caption="📄 Файл конфига WireGuard"
        )
        
        # Отправить JSON бекап
        import json
        backup_json = json.dumps(amnezia_backup, indent=2)
        backup_file = types.BufferedInputFile(
            file=backup_json.encode(),
            filename=f"{config.client_name}_amnezia_backup.json"
        )
        await query.message.answer_document(
            document=backup_file,
            caption="💾 Бекап для приложения Amnezia"
        )
        
        # Отправить инструкцию
        instruction = ConfigManager.create_setup_instruction()
        await query.message.answer(instruction, parse_mode="Markdown")
        
        await query.answer()
