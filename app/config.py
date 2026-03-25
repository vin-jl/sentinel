from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Set centralized application settings via Pydantic BaseSettings
class Settings(BaseSettings):
    sentinel_api_key: str
    gemini_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

# Cache .env keys
@lru_cache
def get_settings() -> Settings:
    return Settings()
