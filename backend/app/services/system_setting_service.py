from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import SystemSetting


def get_public_base_url(db: Session) -> str:
    value = db.scalar(
        select(SystemSetting.setting_value).where(
            SystemSetting.setting_key == "public_base_url"
        )
    )
    if isinstance(value, dict):
        value = value.get("value")
    return value if isinstance(value, str) and value else settings.public_base_url
