import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.database_service import DatabaseService
from src.config import Config

logger = logging.getLogger(__name__)

class NotificationScheduler:
    """Планировщик уведомлений"""
    
    def __init__(self, bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
    
    async def start(self, session_factory):
        """Запустить планировщик"""
        self.scheduler.add_job(
            self.check_expiring_configs,
            "interval",
            hours=1,
            args=(session_factory,),
            id="check_expiring_configs"
        )
        
        self.scheduler.add_job(
            self.delete_expired_configs,
            "interval",
            hours=1,
            args=(session_factory,),
            id="delete_expired_configs"
        )
        
        self.scheduler.start()
        logger.info("Notification scheduler started")
    
    async def check_expiring_configs(self, session_factory):
        """Проверить и отправить уведомления об истечении срока"""
        async with session_factory() as session:
            configs = await DatabaseService.get_expiring_configs(session, days=Config.NOTIFICATION_DAYS)
            
            for config in configs:
                try:
                    # Отправить сообщение пользователю
                    message_text = f"""
⚠️ **Внимание! Скоро истечет срок действия вашего VPN конфига**

📝 Конфиг: `{config.client_name}`
📅 Истекает: `{config.expires_at.strftime('%d.%m.%Y')}`
⏰ Осталось дней: `{config.days_until_expiration()}`

Используйте команду /config или нажмите кнопку "📝 Получить конфиг" для продления на 30 дней.
                    """
                    
                    await self.bot.send_message(
                        chat_id=config.user_id,
                        text=message_text,
                        parse_mode="Markdown"
                    )
                    
                    # Отметить как оповещённый
                    await DatabaseService.mark_as_notified(session, config.config_id)
                    await DatabaseService.log_notification(
                        session,
                        config.config_id,
                        config.user_id,
                        "expiring_warning"
                    )
                    
                    logger.info(f"Sent expiring notification for config {config.config_id}")
                
                except Exception as e:
                    logger.error(f"Failed to send notification for config {config.config_id}: {str(e)}")
    
    async def delete_expired_configs(self, session_factory):
        """Удалить истекшие конфиги"""
        async with session_factory() as session:
            expired_configs = await DatabaseService.get_expired_configs(session)
            
            for config in expired_configs:
                try:
                    # Удалить из WireGuard
                    from src.services.peer_manager import PeerManager
                    await PeerManager.remove_peer(config.client_name, config.client_public_key)
                    
                    # Деактивировать в БД
                    await DatabaseService.deactivate_config(session, config.config_id)
                    
                    # Отправить уведомление
                    message_text = f"""
❌ **Ваш VPN конфиг истек**

📝 Конфиг: `{config.client_name}`
📅 Был действителен до: `{config.expires_at.strftime('%d.%m.%Y')}`

Используйте команду /config или нажмите кнопку "📝 Получить конфиг" для создания нового конфига.
                    """
                    
                    await self.bot.send_message(
                        chat_id=config.user_id,
                        text=message_text,
                        parse_mode="Markdown"
                    )
                    
                    logger.info(f"Deleted expired config {config.config_id}")
                
                except Exception as e:
                    logger.error(f"Failed to delete expired config {config.config_id}: {str(e)}")
    
    async def stop(self):
        """Остановить планировщик"""
        self.scheduler.shutdown()
        logger.info("Notification scheduler stopped")
