from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+pysqlite:///./callparity.db"
    redis_url: str = "redis://localhost:6379/0"
    use_fixtures: bool = True
    calle_base_url: str = "http://fixtures:8080"
    log_level: str = "INFO"
    redis_optional: bool = False
    seed_on_startup: bool = True
    calle_api_token: str = ""
    calle_webhook_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
