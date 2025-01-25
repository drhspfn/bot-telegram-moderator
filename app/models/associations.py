from datetime import datetime

from app.schemas import TelegramUserPermissions
from .base import Base
from sqlalchemy import ForeignKey, TIMESTAMP, Integer, Enum as SQLAlchemyEnum, BigInteger, UniqueConstraint, DateTime
from sqlalchemy.dialects.mysql import JSON
from app.constants import UserRole
from typing import  Optional
from .base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship

class UserChatAssociation(Base):
    __tablename__ = 'telegram_user_chat_association'

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('telegram_users.telegram_id', ondelete="CASCADE"), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('telegram_chats.telegram_id', ondelete="CASCADE"), primary_key=True)
    role: Mapped[UserRole] = mapped_column(SQLAlchemyEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    warn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ban_expires: Mapped[Optional[DateTime]] = mapped_column(TIMESTAMP(timezone=True), default=None, nullable=True)
    mute_expires: Mapped[Optional[DateTime]] = mapped_column(TIMESTAMP(timezone=True), default=None, nullable=True)
    mute_metadata: Mapped[dict] = mapped_column(JSON, default={}, nullable=False)
    ban_metadata: Mapped[dict] = mapped_column(JSON, default={}, nullable=False)

    _privileges: Mapped[dict] = mapped_column("privileges", JSON, default={}, nullable=False)

    user: Mapped["TelegramUser"] = relationship(
        "TelegramUser", 
        back_populates="user_chat_associations",
        overlaps="chats,users"
    )
    chat: Mapped["TelegramChat"] = relationship(
        "TelegramChat", 
        back_populates="user_chat_associations",
        overlaps="users,chats"
    )

    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='uq_user_chat'),
    )

    @property
    def privileges(self) -> TelegramUserPermissions:
        return TelegramUserPermissions(**self._privileges)

    def __repr__(self) -> str:
        return f"<UserChatAssociation(user_id={self.user_id}, chat_id={self.chat_id}, role={self.role})>"


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.mute_metadata is None:
            self.mute_metadata = {}
        if self.ban_metadata is None:
            self.ban_metadata = {}

    