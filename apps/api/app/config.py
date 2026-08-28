from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

CalleMode = Literal["fixture", "live"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./callparity.db"
    redis_url: str = "redis://localhost:6379/0"
    use_fixtures: bool = True
    calle_base_url: str = ""
    log_level: str = "INFO"
    redis_optional: bool = False
    seed_on_startup: bool = True
    calle_api_token: str = ""
    calle_webhook_secret: str = ""
    operator_token: str = ""

    @property
    def calle_mode(self) -> CalleMode:
        return "fixture" if self.use_fixtures else "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
