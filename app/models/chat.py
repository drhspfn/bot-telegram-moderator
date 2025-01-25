from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, create_model
from sqlalchemy import BigInteger, VARCHAR, Enum as SQLAlchemyEnum, TIMESTAMP
from sqlalchemy.dialects.mysql import JSON
from app.schemas import ChatSettings
from .base import Base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.constants import ChatType


class TelegramChat(Base):
    __tablename__ = 'telegram_chats'

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(VARCHAR(64), nullable=False)
    chat_type: Mapped[ChatType] = mapped_column(SQLAlchemyEnum(ChatType))
    _settings: Mapped[dict] = mapped_column("settings", JSON, default={})

    last_init: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=True)

    users: Mapped[List["TelegramUser"]] = relationship(
        "TelegramUser",
        secondary="telegram_user_chat_association",
        back_populates="chats",
        lazy="joined",
        overlaps="user_chat_associations,chats"
    )
    
    user_chat_associations: Mapped[List["UserChatAssociation"]] = relationship(
        "UserChatAssociation",
        back_populates="chat",
        lazy="joined",
        overlaps="users,chats"
    )
    
    @property
    def settings_notify_system_thread_id(self) -> Optional[int]:
        if self.settings.notifications.system_thread_id:
            if self.chat_type is ChatType.PRIVATE: return None
            
            return self.settings.notifications.system_thread_id

        return None 

    @property
    def settings(self) -> Optional[ChatSettings]:
        if not self._settings:
            return None
        return ChatSettings(**self._settings)

    @settings.setter
    def settings(self, value: ChatSettings):

        if value is None:
            self._settings = {}
        else:
            
            self._settings = value.model_dump(mode="json")
    

    def __get_pydantic_core_schema__(self, *args, **kwargs) -> BaseModel:
        return create_model(
            f"{self.__class__.__name__}Schema",
            id=(UUID, ...), 
            telegram_id=(int, ...),
            title=(str, ...),
            chat_type=(ChatType, ...),
            settings=(Dict[str, str], {}), 
            users=(List[Dict], []),
        )
    
    def __repr__(self) -> str:
        return f"<TelegramChat(telegram_id={self.telegram_id}, username='{self.title}')>"