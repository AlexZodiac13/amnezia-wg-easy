from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AmneziaWG Admin"
    secret_key: str = "change-me-in-production"
    admin_username: str = "admin"
    admin_password: str = "admin"
    database_path: str = "data/app.db"
    public_host: str = "127.0.0.1"
    public_port: int = 8000
    server_endpoint_host: str = "vpn.example.com"
    server_endpoint_port: int = 51820
    interface_name: str = "awg0"
    listen_port: int = 51820
    address_pool: str = "10.66.66.0/24"
    server_address: str = "10.66.66.1/24"
    dns_servers: str = "1.1.1.1, 8.8.8.8"
    mtu: int = 1420
    handshake_keepalive: int = 25
    amnezia_jc: int = 4
    amnezia_jmin: int = 8
    amnezia_jmax: int = 80
    amnezia_s1: int = 15
    amnezia_s2: int = 15
    amnezia_h1: int = 5
    amnezia_h2: int = 6
    amnezia_h3: int = 7
    amnezia_h4: int = 8
    awg_binary: str = "awg"
    awg_quick_binary: str = "awg-quick"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
