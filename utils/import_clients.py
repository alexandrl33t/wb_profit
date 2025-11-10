#!/usr/bin/env python3
"""
Скрипт для импорта клиентов из Google таблицы в базу данных.
Получает данные через get_clients() и создает записи в таблицах:
- users (пользователи)
- scripts (скрипты)
- chats (чаты)
- user_script_links (связи пользователей со скриптами)
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from core.config import logger
from core.db import get_session
from models import User, Chat, Script, UserScriptLink
from utils.gspread_utils import get_clients


def check_user_exists(
    db: Session, full_name: str, legal_name_en: str
) -> Optional[User]:
    """
    Проверяет существование пользователя по full_name + legal_name_en.
    """
    return (
        db.query(User)
        .filter(and_(User.full_name == full_name, User.legal_name_en == legal_name_en))
        .first()
    )


def check_script_exists(db: Session, title: str) -> Optional[Script]:
    """
    Проверяет существование скрипта по title.
    """
    return db.query(Script).filter(Script.title == title).first()


def check_chat_exists(db: Session, chat_id: str) -> Optional[Chat]:
    """
    Проверяет существование чата по chat_id.
    """
    return db.query(Chat).filter(Chat.chat_id == chat_id).first()


def check_user_script_link_exists(
    db: Session, report_spreadsheet_key: str, script_id: uuid.UUID
) -> Optional[UserScriptLink]:
    """
    Проверяет существование связи по report_spreadsheet_key + script_id.
    """
    return (
        db.query(UserScriptLink)
        .filter(
            and_(
                UserScriptLink.report_spreadsheet_key == report_spreadsheet_key,
                UserScriptLink.script_id == script_id,
            )
        )
        .first()
    )


def create_user_safe(
    db: Session,
    *,
    full_name: str,
    legal_name_en: str,
    wb_token: Optional[str] = None,
    telegram_user_id: Optional[int] = None,
) -> Optional[User]:
    """
    Создает пользователя с проверкой на существование.
    """
    # Проверяем существование
    existing_user = check_user_exists(db, full_name, legal_name_en)
    if existing_user:
        logger.info(f"  Пользователь уже существует: {full_name} / {legal_name_en}")
        return existing_user

    # Создаем нового пользователя
    user = User(
        full_name=full_name,
        legal_name_en=legal_name_en,
        wb_token=wb_token,
        telegram_user_id=telegram_user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_script_safe(
    db: Session,
    *,
    title: str,
    description: str,
) -> Optional[Script]:
    """
    Создает скрипт с проверкой на существование.
    """
    # Проверяем существование
    existing_script = check_script_exists(db, title)
    if existing_script:
        logger.info(f"  Скрипт уже существует: {title}")
        return existing_script

    # Создаем новый скрипт
    script = Script(title=title, description=description)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def create_chat_safe(
    db: Session,
    *,
    chat_id: str,
    name: str,
) -> Optional[Chat]:
    """
    Создает чат с проверкой на существование.
    """
    # Проверяем существование
    existing_chat = check_chat_exists(db, chat_id)
    if existing_chat:
        logger.info(f"  Чат уже существует: {chat_id}")
        return existing_chat

    # Создаем новый чат
    chat = Chat(chat_id=chat_id, name=name)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def create_user_script_link_safe(
    db: Session,
    *,
    user_id: uuid.UUID,
    script_id: uuid.UUID,
    chat_id: Optional[uuid.UUID] = None,
    enabled: bool = True,
    enabled_until: Optional[datetime] = None,
    report_spreadsheet_key: Optional[str] = None,
) -> Optional[UserScriptLink]:
    """
    Создает связь пользователя со скриптом с проверкой на существование.
    """
    # Проверяем существование
    if report_spreadsheet_key:
        existing_link = check_user_script_link_exists(
            db, report_spreadsheet_key, script_id
        )
        if existing_link:
            logger.info(
                f"  Связь уже существует: {report_spreadsheet_key} + {script_id}"
            )
            return existing_link

    # Создаем новую связь
    link = UserScriptLink(
        user_id=user_id,
        script_id=script_id,
        chat_id=chat_id,
        enabled=enabled,
        enabled_until=enabled_until,
        report_spreadsheet_key=report_spreadsheet_key,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def import_clients_data():
    """
    Основная функция импорта данных из Google таблицы.
    """
    logger.info("Начинаем импорт данных из Google таблицы...")

    # Получаем данные из Google таблицы
    try:
        df = get_clients()
        logger.info(f"Получено {len(df)} записей из Google таблицы")
        logger.info(f"Колонки: {list(df.columns)}")
    except Exception as e:
        logger.error(f"Ошибка при получении данных из Google таблицы: {e}")
        return

    # Получаем сессию базы данных
    db = get_session()

    try:
        # Словари для хранения созданных объектов
        created_scripts: Dict[str, uuid.UUID] = {}  # script_name -> script_id
        created_chats: Dict[str, uuid.UUID] = {}  # chat_id -> chat_id

        # Обрабатываем каждую строку данных
        for index, row in df.iterrows():
            try:
                logger.info(
                    f"\nОбрабатываем строку {index + 1}: {row.get('name', 'Unknown')}"
                )

                # Извлекаем данные из строки
                client = row.get("client", "")
                name = row.get("name", "")
                wb_token = row.get("wb_token", "")
                key_table = row.get("key_table", "")
                script_type = row.get("type", "")
                id_tg = row.get("id_tg", "")

                # Проверяем обязательные поля
                if not name:
                    logger.warning(f"  Пропускаем строку {index + 1}: отсутствует name")
                    continue

                # Создаем пользователя с проверкой
                logger.info(f"  Создаем пользователя: {name}")
                user = create_user_safe(
                    db=db,
                    full_name=client if client else name,
                    legal_name_en=name,
                    wb_token=wb_token if wb_token else None,
                )
                if not user:
                    logger.error(
                        f"  Не удалось создать пользователя для строки {index + 1}"
                    )
                    continue
                logger.info(f"  Пользователь: {user.id}")

                # Создаем скрипт, если его еще нет
                if script_type and script_type not in created_scripts:
                    script_description = f"Скрипт для {script_type}"

                    logger.info(f"  Создаем скрипт: {script_type}")
                    script = create_script_safe(
                        db=db,
                        title=script_type,
                        description=script_description,
                    )
                    if script:
                        created_scripts[script_type] = script.id
                        logger.info(f"  Скрипт: {script.id}")

                # Создаем чат, если указан id_tg
                chat_id = None
                if id_tg:
                    try:
                        tg_chat_id = str(id_tg)  # chat_id теперь строка
                        if tg_chat_id not in created_chats:
                            logger.info(f"  Создаем чат: {name} (TG ID: {tg_chat_id})")
                            chat = create_chat_safe(
                                db=db,
                                chat_id=tg_chat_id,
                                name=name,
                            )
                            if chat:
                                created_chats[tg_chat_id] = chat.id
                                logger.info(f"  Чат: {chat.id}")
                        chat_id = created_chats[tg_chat_id]
                    except Exception as e:
                        logger.error(f"  Ошибка при создании чата: {e}")

                # Связываем пользователя со скриптом
                if script_type in created_scripts:
                    script_id = created_scripts[script_type]

                    # Устанавливаем enabled_until на 100 лет вперед
                    enabled_until = datetime.utcnow() + timedelta(days=365 * 100)

                    logger.info(
                        f"  Связываем пользователя {user.id} со скриптом {script_id}"
                    )
                    link = create_user_script_link_safe(
                        db=db,
                        user_id=user.id,
                        script_id=script_id,
                        chat_id=chat_id,
                        enabled=True,
                        enabled_until=enabled_until,
                        report_spreadsheet_key=key_table if key_table else None,
                    )
                    if link:
                        logger.info(f"  Связь: {link.id}")
                else:
                    logger.warning(
                        f"  Пропускаем связывание: скрипт '{script_type}' не найден"
                    )

            except Exception as e:
                logger.error(f"  Ошибка при обработке строки {index + 1}: {e}")
                continue

        logger.info(f"\nИмпорт завершен!")
        logger.info(f"Создано скриптов: {len(created_scripts)}")
        logger.info(f"Создано чатов: {len(created_chats)}")

    except Exception as e:
        logger.error(f"Ошибка при импорте данных: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import_clients_data()
