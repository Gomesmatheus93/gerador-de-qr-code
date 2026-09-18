import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./qrtracker.db")
    secret_key: str = os.getenv("SECRET_KEY", "")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    environment: str = os.getenv("ENVIRONMENT", "development").lower()
    anonymize_ip: bool = os.getenv("ANONYMIZE_IP", "true").lower() in ("1", "true", "yes")
    geoip_db_path: str = os.getenv("GEOIP_DB_PATH", "")
    trust_proxy_headers: bool = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes")

    @property
    def production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment not in ("development", "test", "production"):
        raise RuntimeError("ENVIRONMENT deve ser development, test ou production.")
    try:
        base = urlsplit(settings.base_url)
        host, port = base.hostname, base.port
    except ValueError as exc:
        raise RuntimeError("BASE_URL inválida.") from exc
    if (base.scheme not in ("http", "https") or not host or port == 0 or base.username or base.password
            or base.query or base.fragment or base.path not in ("", "/")):
        raise RuntimeError("BASE_URL deve ser a origem HTTP(S), sem caminho, query ou fragmento.")
    if settings.production:
        if len(settings.secret_key) < 32 or settings.secret_key.startswith("change-"):
            raise RuntimeError("Configure uma SECRET_KEY forte em produção.")
        if not settings.base_url.startswith("https://"):
            raise RuntimeError("BASE_URL deve usar HTTPS em produção.")
        if not settings.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("Configure PostgreSQL em produção.")
    return settings
