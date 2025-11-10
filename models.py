import uuid
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import (
    Boolean,
    Index,
    String,
    Text,
    BigInteger,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, LargeBinary

from core.config import settings


# ---------- Шифрование (прозрачный тип для чувствительных строк) ----------
class EncryptedString(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fernet = Fernet(
            settings.fernet_key.encode()
            if isinstance(settings.fernet_key, str)
            else settings.fernet_key
        )

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode("utf-8")
        return self._fernet.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        decrypted = self._fernet.decrypt(value)
        return decrypted.decode("utf-8")


# ---------- База и общий миксин ----------
class Base(DeclarativeBase):
    pass


class TimestampedMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


# ---------- Таблицы юзеров ----------
class User(TimestampedMixin, Base):
    __tablename__ = "users"

    # ФИО клиента
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Название ИП на английском (как просили "name")
    legal_name_en: Mapped[str] = mapped_column(String(255), nullable=False)

    # Токен WB — шифруем
    wb_token: Mapped[Optional[str]] = mapped_column(EncryptedString, nullable=True)

    # Личные сообщения в TG — опционально
    telegram_user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, unique=True
    )

    # связи
    subscriptions: Mapped[list["UserScriptLink"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Chat(TimestampedMixin, Base):
    __tablename__ = "chats"

    # TG chat_id и имя чата
    chat_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # связи
    subscriptions: Mapped[list["UserScriptLink"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )


class Script(TimestampedMixin, Base):
    __tablename__ = "scripts"
    # Человекочитаемое имя и описание
    title: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    subscriptions: Mapped[list["UserScriptLink"]] = relationship(
        back_populates="script", cascade="all, delete-orphan"
    )


class UserScriptLink(TimestampedMixin, Base):
    """
    Связка пользователь × скрипт × (куда слать уведомления) с параметрами подписки.
    """

    __tablename__ = "user_script_links"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )

    # Флаг активности
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # До какого времени действует подписка (UTC)
    enabled_until: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Отчётная таблица/лист для конкретного скрипта (если на скрипт нужен отдельный ключ)
    report_spreadsheet_key: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # связи
    user: Mapped["User"] = relationship(back_populates="subscriptions")
    script: Mapped["Script"] = relationship(back_populates="subscriptions")
    chat: Mapped[Optional["Chat"]] = relationship(back_populates="subscriptions")

    __table_args__ = (
        UniqueConstraint("user_id", "script_id", name="uq_user_script_unique"),
        Index("ix_links_user", "user_id"),
        Index("ix_links_script", "script_id"),
        Index("ix_links_chat", "chat_id"),
        Index("ix_links_enabled_until", "enabled_until"),
    )


# # ---------- Каталог товаров и метрики (история прибыли/выручки) ----------
# class Product(TimestampedMixin, Base):
#     __tablename__ = "products"
#
#     # Владелец ассортимента
#     user_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
#     )
#
#     # Код артикула (supplierArticle / vendorCode)
#     article: Mapped[str] = mapped_column(String(128), nullable=False)
#
#     __table_args__ = (
#         UniqueConstraint("user_id", "article", name="uq_product_user_article"),
#         Index("ix_products_user", "user_id"),
#         Index("ix_products_article", "article"),
#     )
#
#
# class ArticleMetric(TimestampedMixin, Base):
#     __tablename__ = "article_metrics"
#
#     # Какой товар
#     product_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True),
#         ForeignKey("products.id", ondelete="CASCADE"),
#         nullable=False,
#     )
#
#     # Округлённый до часа момент времени (UTC)
#     date_hour: Mapped[datetime] = mapped_column(
#         TIMESTAMP(timezone=True), nullable=False, index=True
#     )
#
#     # Имя метрики: например, "profit" или "revenue"
#     metric_name: Mapped[str] = mapped_column(String(32), nullable=False)
#
#     # Значение метрики
#     value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
#
#     __table_args__ = (
#         UniqueConstraint(
#             "product_id", "date_hour", "metric_name", name="uq_metric_unique"
#         ),
#         Index("ix_metrics_product_hour", "product_id", "date_hour"),
#         Index("ix_metrics_product_metric", "product_id", "metric_name"),
#     )
#
#
# class UserTotals(TimestampedMixin, Base):
#     __tablename__ = "user_totals"
#
#     # Владелец суммарных показателей
#     user_id: Mapped[uuid.UUID] = mapped_column(
#         UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
#     )
#
#     # Часовой срез (UTC)
#     date_hour: Mapped[datetime] = mapped_column(
#         TIMESTAMP(timezone=True), nullable=False, index=True
#     )
#
#     # Суммарные показатели за этот час
#     total_profit: Mapped[Decimal] = mapped_column(
#         Numeric(18, 2), nullable=False, default=0
#     )
#     total_revenue: Mapped[Decimal] = mapped_column(
#         Numeric(18, 2), nullable=False, default=0
#     )
#
#     __table_args__ = (
#         UniqueConstraint("user_id", "date_hour", name="uq_user_totals_unique"),
#         Index("ix_totals_user_hour", "user_id", "date_hour"),
#     )
