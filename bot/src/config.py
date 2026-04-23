import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
    
    # Database
    DATABASE_URL = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    
    # AWG
    AWG_INTERFACE = os.getenv("AWG_INTERFACE", "awg0")
    AWG_LISTEN_PORT = int(os.getenv("AWG_LISTEN_PORT", "5060"))
    AWG_SUBNET = os.getenv("AWG_SUBNET", "10.80.0.1/24")
    AWG_DNS = os.getenv("AWG_DNS", "10.80.0.1")
    AWG_CONTAINER_NAME = os.getenv("AWG_CONTAINER_NAME", "awg-core")
    
    # Paths
    SCRIPTS_DIR = os.getenv("SCRIPTS_DIR", "/app/scripts")
    CONFIGS_DIR = os.getenv("CONFIGS_DIR", "/etc/amnezia/amneziawg/clients")
    
    # Rate limits
    DEFAULT_RATE_LIMIT = int(os.getenv("DEFAULT_RATE_LIMIT", "15"))
    
    # Expiration
    EXPIRATION_DAYS = int(os.getenv("EXPIRATION_DAYS", "30"))
    NOTIFICATION_DAYS = int(os.getenv("NOTIFICATION_DAYS", "3"))
