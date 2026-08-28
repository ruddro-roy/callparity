from functools import lru_cache
from typing import Literal

from pydantic import field_validator
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
    # Mutating operator routes. 0 disables the limiter (tests / CI).
    mutating_rate_limit: int = 60
    mutating_rate_window_seconds: int = 60

    @field_validator("operator_token")
    @classmethod
    def _reject_empty_token_segments(cls, value: str) -> str:
        # OPERATOR_TOKEN may hold several comma-separated tokens during a
        # rotation window. A value like "a,,b" or a lone comma is a config
        # mistake; refuse to boot rather than silently carry an empty token.
        if "," in value and any(not segment.strip() for segment in value.split(",")):
            raise ValueError(
                "OPERATOR_TOKEN segments must be non-empty; "
                "separate rotation tokens with single commas"
            )
        return value

    @property
    def operator_tokens(self) -> tuple[str, ...]:
        """Configured operator tokens: one normally, several mid-rotation."""
        return tuple(token.strip() for token in self.operator_token.split(",") if token.strip())

    @property
    def calle_mode(self) -> CalleMode:
        return "fixture" if self.use_fixtures else "live"


@lru_cache
def get_settings() -> Settings:
    return Settings()
