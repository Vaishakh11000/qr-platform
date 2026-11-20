
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application settings
    app_name: str = "QR Product Information Platform"
    app_version: str = "1.0.0"
    debug: bool = False

    # Admin authentication
    admin_token_secret: SecretStr = Field(min_length=64)
    admin_access_token_expire_minutes: int = Field(
        default=30, ge=5, le=1440
    )

    # Public address encoded into generated QR codes.
    public_base_url: str = "http://localhost:8000"

    # Persistent root for product images and documents.
    media_storage_root: Path = PROJECT_ROOT / "storage"

    # Production database settings
    postgres_db: str = "qr_platform"
    postgres_user: str = "qr_app"
    postgres_password: SecretStr

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    # Dedicated testing database
    test_postgres_db: str = "qr_platform_test"

    @property
    def database_url(self) -> URL:
        """Production database connection URL."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
            query={"options": "-csearch_path=app,public"},
        )

    @property
    def test_database_url(self) -> URL:
        """Dedicated test database connection URL."""
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.test_postgres_db,
            query={"options": "-csearch_path=app,public"},
        )


# Load and validate configuration once.
settings = Settings()
