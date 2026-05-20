import sys
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from src.database.models import Base, Config
from src.services.database_service import DatabaseService


@pytest.fixture()
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_default_user_config_expires_after_30_days(async_session):
    user = await DatabaseService.create_user(async_session, telegram_id=123456789, username="testuser")
    now = datetime.utcnow()

    config = await DatabaseService.create_config(
        session=async_session,
        user_id=user.id,
        config_id="test-config-30d",
        client_name="test-client",
        client_private_key="private-key",
        client_public_key="public-key",
        client_preshared_key="preshared-key",
        client_ip="10.0.0.10",
        wg_config_content="[Interface]"
    )

    delta = config.expires_at - now
    assert timedelta(days=29, minutes=55) <= delta <= timedelta(days=30, minutes=5)


@pytest.mark.asyncio
async def test_expiring_and_expired_config_queries(async_session):
    user = await DatabaseService.create_user(async_session, telegram_id=987654321, username="testuser2")
    now = datetime.utcnow()

    expiring_config = Config(
        user_id=user.id,
        config_id="expiring-config",
        client_name="expiring-client",
        client_private_key="private-key",
        client_public_key="public-key",
        client_preshared_key="preshared-key",
        client_ip="10.0.0.11",
        wg_config_content="[Interface]",
        expires_at=now + timedelta(days=3),
        notified_at=None,
        is_active=True,
    )

    expired_config = Config(
        user_id=user.id,
        config_id="expired-config",
        client_name="expired-client",
        client_private_key="private-key",
        client_public_key="public-key",
        client_preshared_key="preshared-key",
        client_ip="10.0.0.12",
        wg_config_content="[Interface]",
        expires_at=now - timedelta(days=1),
        notified_at=None,
        is_active=True,
    )

    async_session.add_all([expiring_config, expired_config])
    await async_session.commit()

    expiring = await DatabaseService.get_expiring_configs(async_session, days=3)
    expired = await DatabaseService.get_expired_configs(async_session)

    expiring_ids = {config.config_id for config in expiring}
    expired_ids = {config.config_id for config in expired}

    assert "expiring-config" in expiring_ids
    assert "expired-config" not in expiring_ids
    assert "expired-config" in expired_ids
    assert "expiring-config" not in expired_ids
