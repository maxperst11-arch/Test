from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from typing import Annotated


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    # Пустой список означает, что бот доступен всем.
    allowed_user_ids: Annotated[list[int], NoDecode] = []
    default_timezone: str = "Europe/Moscow"
    database_path: str = "data/magic_boot.db"

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [int(part) for part in value.replace(" ", "").split(",") if part]
        return value

    def is_allowed(self, user_id: int) -> bool:
        return not self.allowed_user_ids or user_id in self.allowed_user_ids
