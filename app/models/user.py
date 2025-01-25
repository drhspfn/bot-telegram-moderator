from typing import List, Optional
from uuid import UUID
from sqlalchemy import VARCHAR, BigInteger
from .base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
class TelegramUser(Base):
    __tablename__ = 'telegram_users'

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(VARCHAR(64), nullable=True)

    chats: Mapped[List["TelegramChat"]] = relationship(
        "TelegramChat",
        secondary="telegram_user_chat_association",
        back_populates="users",
        lazy="joined",
        overlaps="user_chat_associations,users"
    )

    user_chat_associations: Mapped[List["UserChatAssociation"]] = relationship(
        "UserChatAssociation",
        back_populates="user",
        lazy="joined",
        overlaps="chats,users"
    )

    def get_association(self, chat_id: int) -> Optional["UserChatAssociation"]:
        for association in self.user_chat_associations:
            if association.chat_id == chat_id:
                return association
    
    def __repr__(self) -> str:
        return f"<TelegramUser(telegram_id={self.telegram_id}, username='{self.username}')>"