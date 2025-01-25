from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, validator
from typing import Any, List, Optional, Literal
from aiogram import types
from app import constants
from app.classes import DurationString

class ChatSettingsPunishment(BaseModel):
    type: Literal["ban", "mute"]
    duration: Optional[DurationString] = "30m"
    warning_threshold: Optional[int] = 3

    @validator('duration', pre=True)
    def validate_duration(cls, value) -> DurationString:
        if isinstance(value, str):
            return DurationString(value)
        
        return value
    
    class Config(ConfigDict):
        arbitrary_types_allowed = True

class ChatSettingsRestrictedWords(BaseModel):
    enabled: bool
    words: Optional[List[str]] = []
    punishment: ChatSettingsPunishment


class ChatSettingsReadRules(BaseModel):
    enabled: bool
    url: str

class ChatSettingsModeration(BaseModel):
    enabled: bool
    read_rules: ChatSettingsReadRules


class ChatSettingsNotifications(BaseModel):
    new_user_notifications: bool
    left_user_notifications: bool

    system_thread_id: Optional[int] = None
    new_user_thread_id: Optional[int] = None
    
    
class ChatSettingsLinkFiltering(BaseModel):
    enabled: bool
    block_all: bool
    whitelist: Optional[List[str]] = []


class ChatSettings(BaseModel):
    moderation: ChatSettingsModeration
    notifications: ChatSettingsNotifications
    restricted_words: ChatSettingsRestrictedWords
    link_filtering: ChatSettingsLinkFiltering


class BotUserStateEdit(BaseModel):
    selected_chat_id: Optional[UUID] = None
    selected_chat_tid: Optional[int]= None
    settings: Optional[ChatSettings]= None

class BotUserState(BaseModel):
    user_id: int
    edit: Optional[BotUserStateEdit] = None
    state: Optional[constants.UserState] = None
    last_message_id: Optional[int] = None
    last_inline_message_id: Optional[int] = None

    read_rules_start: Optional[datetime] = None

class TelegramUserSchema(BaseModel):
    id: UUID
    telegram_id: int
    username: Optional[str] = None
    chats: Optional[List[Any]] = []

    class Config:
        from_attributes  = True

class TelegramChatSchema(BaseModel):
    id: UUID
    telegram_id: int
    title: str
    chat_type: constants.ChatType
    settings: ChatSettings
    users: Optional[List[TelegramUserSchema]] = []

    class Config:
        from_attributes  = True



class TelegramUserPermissions(BaseModel):
    is_member : Optional[bool] = False
    """:code:`True`, if the user is a member of the chat at the moment of the request"""
    can_send_messages: Optional[bool] = False
    """:code:`True`, if the user is allowed to send text messages, contacts, giveaways, giveaway winners, invoices, locations and venues"""
    can_send_audios: Optional[bool] = False
    """:code:`True`, if the user is allowed to send audios"""
    can_send_documents: Optional[bool] = False
    """:code:`True`, if the user is allowed to send documents"""
    can_send_photos: Optional[bool] = False
    """:code:`True`, if the user is allowed to send photos"""
    can_send_videos: Optional[bool] = False
    """:code:`True`, if the user is allowed to send videos"""
    can_send_video_notes: Optional[bool] = False
    """:code:`True`, if the user is allowed to send video notes"""
    can_send_voice_notes: Optional[bool] = False
    """:code:`True`, if the user is allowed to send voice notes"""
    can_send_polls: Optional[bool] = False
    """:code:`True`, if the user is allowed to send polls"""
    can_send_other_messages: Optional[bool] = False
    """:code:`True`, if the user is allowed to send animations, games, stickers and use inline bots"""
    can_add_web_page_previews: Optional[bool] = False
    """:code:`True`, if the user is allowed to add web page previews to their messages"""
    can_change_info: Optional[bool] = False
    """:code:`True`, if the user is allowed to change the chat title, photo and other settings"""
    can_invite_users: Optional[bool] = False
    """:code:`True`, if the user is allowed to invite new users to the chat"""
    can_pin_messages: Optional[bool] = False
    """:code:`True`, if the user is allowed to pin messages"""
    can_manage_topics: Optional[bool] = False
    """:code:`True`, if the user is allowed to create forum topics"""

    can_be_edited: Optional[bool] = True
    can_restrict_members: Optional[bool] = False
    can_delete_messages: Optional[bool] = False

    # 
    @staticmethod
    def from_user(user: list[types.ChatMemberOwner | types.ChatMemberAdministrator | types.ChatMemberMember | types.ChatMemberRestricted | types.ChatMemberLeft | types.ChatMemberBanned]):
        try:
            dict_user = user.__dict__
            is_member = dict_user.get('is_member', True)
            can_send_messages = dict_user.get('can_send_messages', True)
            can_send_audios = dict_user.get('can_send_audios', False)
            can_send_documents = dict_user.get('can_send_documents', False)
            can_send_photos = dict_user.get('can_send_photos', False)
            can_send_videos = dict_user.get('can_send_videos', False)
            can_send_video_notes = dict_user.get('can_send_video_notes', False)
            can_send_polls = dict_user.get('can_send_polls', False)
            can_send_other_messages = dict_user.get('can_send_other_messages', False)
            can_add_web_page_previews = dict_user.get('can_add_web_page_previews', True)
            can_change_info = dict_user.get('can_change_info')
            if not can_change_info:
                can_manage_chat = dict_user.get('can_manage_chat')
                if can_manage_chat:
                    can_change_info = True
                else: can_change_info = False


            can_invite_users = dict_user.get('can_invite_users', True)
            can_pin_messages = dict_user.get('can_pin_messages', False)
            can_manage_topics = dict_user.get('can_manage_topics', False)
            can_be_edited = dict_user.get('can_be_edited', True)
            can_restrict_members = dict_user.get('can_restrict_members', False)
            can_delete_messages = dict_user.get('can_delete_messages', False)
            return TelegramUserPermissions(
                is_member=is_member,
                can_send_messages=can_send_messages,
                can_send_audios=can_send_audios,
                can_send_documents=can_send_documents,
                can_send_photos=can_send_photos,
                can_send_videos=can_send_videos,
                can_send_video_notes=can_send_video_notes,
                can_send_polls=can_send_polls,
                can_send_other_messages=can_send_other_messages,
                can_add_web_page_previews=can_add_web_page_previews,
                can_change_info=can_change_info,
                can_invite_users=can_invite_users,
                can_pin_messages=can_pin_messages,
                can_manage_topics=can_manage_topics,
                can_be_edited=can_be_edited,
                can_restrict_members=can_restrict_members,
                can_delete_messages=can_delete_messages
            )
        except Exception as e:
            return TelegramUserPermissions()