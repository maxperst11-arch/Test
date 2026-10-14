from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    # Telegram ID или @username через запятую. Пустой список — бот доступен всем.
    allowed_users: Annotated[list[str], NoDecode] = []
    default_timezone: str = "Europe/Moscow"
    database_path: str = "data/magic_boot.db"

    @field_validator("allowed_users", mode="before")
    @classmethod
    def parse_users(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.split(",")
        return [str(item).strip().lstrip("@").lower() for item in value if str(item).strip()]

    def is_allowed(self, user_id: int, username: str | None) -> bool:
        if not self.allowed_users:
            return True
        return str(user_id) in self.allowed_users or (
            username is not None and username.lower() in self.allowed_users
        )
