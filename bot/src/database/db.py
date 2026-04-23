import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.config import Config
from src.database.models import Base

engine = None
async_session = None

async def init_db():
    global engine, async_session
    engine = create_async_engine(Config.DATABASE_URL, echo=False, pool_size=10, max_overflow=20)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_session():
    if async_session is None:
        raise RuntimeError("Database not initialized")
    async with async_session() as session:
        yield session

async def close_db():
    if engine:
        await engine.dispose()

async def check_db_connection():
    """Check PostgreSQL connection"""
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection error: {e}")
        return False
