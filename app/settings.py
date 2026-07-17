from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    OPENALEX_API_KEY: str

    model_config = SettingsConfigDict(
        env_file='.env',
        extra='ignore'
    )

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()