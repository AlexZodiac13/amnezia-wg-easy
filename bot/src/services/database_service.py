from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from src.database.models import Config, User, NotificationLog
from src.config import Config as AppConfig
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """Сервис для работы с БД"""
    
    @staticmethod
    async def create_user(session: AsyncSession, telegram_id: int, username: str = None, is_admin: bool = False) -> User:
        """Создать нового пользователя"""
        is_admin = is_admin or telegram_id == AppConfig.ADMIN_TELEGRAM_ID
        user = User(telegram_id=telegram_id, username=username, is_admin=is_admin)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    
    @staticmethod
    async def get_user(session: AsyncSession, telegram_id: int) -> User:
        """Получить пользователя по Telegram ID"""
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_user(session: AsyncSession, telegram_id: int, username: str = None) -> User:
        """Получить или создать пользователя"""
        user = await DatabaseService.get_user(session, telegram_id)
        if user is None:
            return await DatabaseService.create_user(session, telegram_id, username)

        if telegram_id == AppConfig.ADMIN_TELEGRAM_ID and not user.is_admin:
            user.is_admin = True
            await session.commit()
            await session.refresh(user)

        return user

    @staticmethod
    async def create_config(
        session: AsyncSession,
        user_id: int,
        config_id: str,
        client_name: str,
        client_private_key: str,
        client_public_key: str,
        client_preshared_key: str,
        client_ip: str,
        wg_config_content: str,
        rate_limit: int = 15,
        expires_at: datetime | None = None
    ) -> Config:
        """Создать новый конфиг"""
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(days=AppConfig.EXPIRATION_DAYS)
        config = Config(
            user_id=user_id,
            config_id=config_id,
            client_name=client_name,
            client_private_key=client_private_key,
            client_public_key=client_public_key,
            client_preshared_key=client_preshared_key,
            client_ip=client_ip,
            wg_config_content=wg_config_content,
            rate_limit=rate_limit,
            expires_at=expires_at
        )
        session.add(config)
        await session.commit()
        await session.refresh(config)
        return config
    
    @staticmethod
    async def get_active_config(session: AsyncSession, user_id: int) -> Config:
        """Получить активный конфиг пользователя"""
        result = await session.execute(
            select(Config).where(
                and_(
                    Config.user_id == user_id,
                    Config.is_active == True,
                    Config.expires_at > datetime.utcnow()
                )
            ).order_by(Config.created_at.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def get_active_client_ips(session: AsyncSession) -> list[str]:
        """Получить IP-адреса активных конфигов"""
        result = await session.execute(
            select(Config.client_ip).where(
                and_(
                    Config.is_active == True,
                    Config.expires_at > datetime.utcnow()
                )
            )
        )
        return [row[0] for row in result.all()]
    
    @staticmethod
    async def get_config_by_id(session: AsyncSession, config_id: str) -> Config:
        """Получить конфиг по ID"""
        result = await session.execute(select(Config).where(Config.config_id == config_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def deactivate_config(session: AsyncSession, config_id: str):
        """Деактивировать конфиг"""
        config = await DatabaseService.get_config_by_id(session, config_id)
        if config:
            config.is_active = False
            await session.commit()
    
    @staticmethod
    async def get_expiring_configs(session: AsyncSession, days: int = 3) -> list:
        """Получить конфиги, срок которых заканчивается через N дней"""
        expiration_start = datetime.utcnow() + timedelta(days=days - 1)
        expiration_end = datetime.utcnow() + timedelta(days=days + 1)
        
        result = await session.execute(
            select(Config).where(
                and_(
                    Config.expires_at >= expiration_start,
                    Config.expires_at <= expiration_end,
                    Config.is_active == True,
                    Config.notified_at == None
                )
            )
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_expired_configs(session: AsyncSession) -> list:
        """Получить истекшие конфиги"""
        result = await session.execute(
            select(Config).where(
                and_(
                    Config.expires_at <= datetime.utcnow(),
                    Config.is_active == True
                )
            )
        )
        return result.scalars().all()
    
    @staticmethod
    async def mark_as_notified(session: AsyncSession, config_id: str):
        """Отметить конфиг как оповещённый"""
        config = await DatabaseService.get_config_by_id(session, config_id)
        if config:
            config.notified_at = datetime.utcnow()
            await session.commit()
    
    @staticmethod
    async def log_notification(session: AsyncSession, config_id: str, user_id: int, notification_type: str):
        """Логировать отправку уведомления"""
        log = NotificationLog(
            config_id=config_id,
            user_id=user_id,
            notification_type=notification_type
        )
        session.add(log)
        await session.commit()
    
    @staticmethod
    async def get_user_count(session: AsyncSession) -> int:
        """Получить количество активных пользователей"""
        result = await session.execute(select(User))
        return len(result.scalars().all())
    
    @staticmethod
    async def get_all_users(session: AsyncSession) -> list:
        """Получить всех пользователей"""
        result = await session.execute(select(User))
        return result.scalars().all()
    
    @staticmethod
    async def delete_user_with_configs(session: AsyncSession, user_id: int):
        """Удалить пользователя со всеми конфигами"""
        configs = await session.execute(select(Config).where(Config.user_id == user_id))
        for config in configs.scalars():
            await session.delete(config)
        
        user = await session.execute(select(User).where(User.id == user_id))
        user_obj = user.scalar_one_or_none()
        if user_obj:
            await session.delete(user_obj)
        
        await session.commit()
