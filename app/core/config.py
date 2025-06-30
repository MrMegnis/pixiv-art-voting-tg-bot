from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )

    bot_token: str
    admin_password: str
    pixiv_refresh_token: str # Добавили

settings = Settings()