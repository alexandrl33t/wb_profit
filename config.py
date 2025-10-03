from pathlib import Path

import telebot
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Секреты
    tg_bot_token: str = Field(..., description="Токен Telegram-бота")
    data_key: str = Field(..., description="Секретный ключ для работы с данными")

    # Google credentials
    gspread_credentials_file: Path = Field(
        "credentials.json", description="Путь к JSON с credentials для Google API"
    )

    model_config = SettingsConfigDict(
        env_file=".env",  # можно хранить локально .env
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()


bot = telebot.TeleBot(settings.tg_bot_token)
