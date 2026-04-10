import secrets

from passlib.context import CryptContext

from app.config import Settings


pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def create_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def is_valid_admin_login(settings: Settings, username: str, password: str) -> bool:
    return username == settings.admin_username and password == settings.admin_password


def generate_token() -> str:
    return secrets.token_urlsafe(32)
