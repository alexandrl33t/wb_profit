import logging
import sys
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

    fernet_key: str = Field(..., description="Ключ шифрования")

    # Database settings
    db_user: str = Field(default="postgres", description="Имя пользователя базы данных")
    db_password: str = Field(default="", description="Пароль базы данных")
    db_host: str = Field(default="localhost", description="Хост базы данных")
    db_port: str = Field(default="5432", description="Порт базы данных")
    db_name: str = Field(default="postgres", description="Имя базы данных")

    model_config = SettingsConfigDict(
        env_file=".env",  # можно хранить локально .env
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
    )


settings = Settings()


def setup_logger(name: str = "wb_profit", level: str = "INFO") -> logging.Logger:
    """
    Настраивает логгер для проекта.
    """
    logger = logging.getLogger(name)
    
    # Устанавливаем уровень логирования
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Проверяем, есть ли уже обработчики
    if logger.handlers:
        return logger
    
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Создаем обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Создаем обработчик для файла
    file_handler = logging.FileHandler('wb_profit.log', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Добавляем обработчики к логгеру
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# Создаем основной логгер
logger = setup_logger()

bot = telebot.TeleBot(settings.tg_bot_token)
