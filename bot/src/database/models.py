from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, LargeBinary, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(unique=True, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

class Config(Base):
    __tablename__ = "configs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[int] = mapped_column(index=True)
    client_name: Mapped[str] = mapped_column(String(255))
    client_private_key: Mapped[str] = mapped_column(Text)
    client_public_key: Mapped[str] = mapped_column(Text)
    client_preshared_key: Mapped[str] = mapped_column(Text)
    client_ip: Mapped[str] = mapped_column(String(50))
    rate_limit: Mapped[int] = mapped_column(default=15)  # Mbit/s
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column()
    notified_at: Mapped[datetime] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    wg_config_content: Mapped[str] = mapped_column(Text, nullable=True)
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def days_until_expiration(self) -> int:
        return (self.expires_at - datetime.utcnow()).days

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    notification_type: Mapped[str] = mapped_column(String(50))  # "3_days_warning", "expired"
    sent_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
