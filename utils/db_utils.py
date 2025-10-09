from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy.orm import Session

from models import User, Chat, Script, UserScriptLink


def insert_user(
    db: Session,
    *,
    full_name: str,
    legal_name_en: str,
    wb_token: Optional[str] = None,
    gspread_key: Optional[str] = None,
    telegram_user_id: Optional[int] = None,
) -> User:
    user = User(
        full_name=full_name,
        legal_name_en=legal_name_en,
        wb_token=wb_token,
        gspread_key=gspread_key,
        telegram_user_id=telegram_user_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def insert_chat(
    db: Session,
    *,
    chat_id: int,
    name: str,
) -> Chat:
    chat = Chat(chat_id=chat_id, name=name)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def insert_script(
    db: Session,
    *,
    code: str,
    title: str,
    description: str,
) -> Script:
    script = Script(code=code, title=title, description=description)
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def insert_user_script_link(
    db: Session,
    *,
    user_id: uuid.UUID,
    script_id: uuid.UUID,
    chat_id: Optional[uuid.UUID] = None,
    enabled: bool = True,
    enabled_until: Optional[datetime] = None,
    report_spreadsheet_key: Optional[str] = None,
) -> UserScriptLink:
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
