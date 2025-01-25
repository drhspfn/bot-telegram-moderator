from datetime import datetime
from typing import Any, List, Literal, Optional, Tuple, Union
from uuid import UUID
from sqlalchemy import func, update, delete
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app import constants
from app.bad_word import is_toxic_message
from app.cache import get_chat_state, get_user_state, set_chat_state, clear_chat_state
from app.classes import DurationString
from app.database import get_session
from app.models import TelegramUser, TelegramChat, UserChatAssociation
from app.schemas import BotUserState, ChatSettings, TelegramChatSchema, TelegramUserPermissions
from app.utils import extract_urls, to_timestamp, utcnow

from aiogram.types import User

async def get_user_by_username(
    session: AsyncSession, 
    username: str
) -> Optional[TelegramUser]:
    query = select(TelegramUser).where(TelegramUser.username == username)
    result = await session.execute(query)
    user:Optional[TelegramUser] = result.unique().scalar_one_or_none()
    return user

async def get_or_create_user(
    session: AsyncSession, 
    telegram_id: int, 
    username: str = None
) -> TelegramUser:
    query = select(TelegramUser).where(TelegramUser.telegram_id == telegram_id)
    result = await session.execute(query)
    user:Optional[TelegramUser] = result.unique().scalar_one_or_none()
    
    if not user:
        user = TelegramUser(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        return user
    
    if username is not None and user.username != username:
        user.username = username
        await session.commit()
    
    return user

async def get_or_create_chat(
    session: AsyncSession, 
    telegram_id: int, 
    title: str, 
    chat_type: constants.ChatType
) -> TelegramChat:
    query = select(TelegramChat).where(TelegramChat.telegram_id == telegram_id)
    result = await session.execute(query)
    chat:Optional[TelegramChat] = result.unique().scalar_one_or_none()
    
    if not chat:
        settings = {} if chat_type == constants.ChatType.PRIVATE else constants.DEFAULT_CHAT_SETTINGS
        
        chat = TelegramChat(
            telegram_id=telegram_id,
            title=title,
            chat_type=chat_type,
            _settings=settings
        )
        session.add(chat)
        await session.commit()
        
        # await set_chat_state(chat.telegram_id, chat)
        return chat
    
    # await set_chat_state(chat.telegram_id, chat)
    return chat

async def get_user_by(
    session: AsyncSession,
    identifier: Union[int, UUID],
    load_relations: bool = True
) -> Optional[TelegramUser]:
    if isinstance(identifier, int):
        query = select(TelegramUser).where(TelegramUser.telegram_id == identifier)
    elif isinstance(identifier, UUID):
        query = select(TelegramUser).where(TelegramUser.id == identifier)
    else:
        raise ValueError("Invalid identifier type")
    
    if load_relations:
        query = query.options(
            selectinload(TelegramUser.chats).load_only(
                TelegramChat.id,
                TelegramChat.telegram_id,
                TelegramChat.title,
                TelegramChat.chat_type,
                TelegramChat._settings
            )
        )
        
    result = await session.execute(query)
    return result.unique().scalar_one_or_none()

async def get_chat_by(
    session: AsyncSession,
    identifier: Union[int, UUID],
    load_relations: bool = True
) -> Optional[TelegramChat]:
    if isinstance(identifier, int):
        query = select(TelegramChat).where(TelegramChat.telegram_id == identifier)
    else:
        query = select(TelegramChat).where(TelegramChat.id == str(identifier))
    
    if load_relations:
        query = query.options(
            selectinload(TelegramChat.users).load_only(
                TelegramUser.id,
                TelegramUser.telegram_id,
                TelegramUser.username
            )
        )
        
    result = await session.execute(query)
    chat = result.unique().scalar_one_or_none()

    if chat:
        await set_chat_state(chat.telegram_id, chat)


    return chat

async def get_association(
    session:AsyncSession, 
    user_id: int, 
    chat_id: int
) -> Optional[UserChatAssociation]:
    association = await session.execute(
        select(UserChatAssociation)
        .where(
            UserChatAssociation.user_id == user_id,
            UserChatAssociation.chat_id == chat_id
        )
        .options(selectinload(UserChatAssociation.user), selectinload(UserChatAssociation.chat)) 
    )
    return  association.scalars().first()


async def get_or_create_association(
    session:AsyncSession, 
    user_id: int, 
    chat_id: int,
    user_role: Optional[constants.UserRole] = None,
    warn_count: Optional[int] = None,
    privileges: Optional[TelegramUserPermissions] = None
) -> UserChatAssociation:
    association_record = await get_association(session, user_id, chat_id)

    if association_record:
        if user_role and association_record.role != user_role:
            association_record.role = user_role

        if warn_count and association_record.warn_count != warn_count: 
            association_record.warn_count = warn_count
        
        await session.commit() 
    else:
        association_record = UserChatAssociation(
            user_id=user_id,
            chat_id=chat_id,
            role=user_role,
            warn_count = warn_count,
            _privileges = privileges.model_dump(mode="json") if privileges else {}
        )
        session.add(association_record)
        await session.commit()

    return association_record


async def get_user_chats(
    session: AsyncSession,
    user: TelegramUser,
    roles: Optional[List[constants.UserRole]] = [
        constants.UserRole.OWNER, constants.UserRole.ADMIN]
) -> List["TelegramChat"]:
    query = select(TelegramChat).join(
        UserChatAssociation
    ).where(
        UserChatAssociation.user_id == user.telegram_id
    )

    if roles:
        query = query.where(UserChatAssociation.role.in_(roles))

    query = query.options(
        selectinload(TelegramChat.users).load_only(
            TelegramUser.id,
            TelegramUser.telegram_id,
            TelegramUser.username
        )
    )
    # Compile and print the query

    result = await session.execute(query)
    chats = result.scalars().unique().all()
    return chats

async def get_chat_from_cache(chat_id: UUID | int) -> Optional[TelegramChatSchema]:
    chat_state = await get_chat_state(chat_id)
    if not chat_state:
        async with get_session() as session:
            chat = await get_chat_by(session, chat_id)
            chat_state = await get_chat_state(chat_id)
        
    return chat_state


async def update_chat_settings_by_id(
    session: AsyncSession, 
    identifier: Union[int, UUID], 
    settings: ChatSettings
):
    settings_dict = settings.model_dump(mode="json")

    if isinstance(identifier, UUID):
        query = update(TelegramChat).where(TelegramChat.id == str(identifier))
    else:
        query = update(TelegramChat).where(TelegramChat.telegram_id == identifier)

    await session.execute(query.values(_settings=settings_dict))
    await session.commit()
    await clear_chat_state(identifier)


async def proccess_left_member(user_id: int, chat_id:int, session:AsyncSession) -> bool:
    try:
        await session.execute(
            delete(UserChatAssociation)
        .where(
                UserChatAssociation.user_id == user_id,
                UserChatAssociation.chat_id == chat_id
            )
        )
        await session.commit()
        return True
    
    except Exception as e:
        print(f"Error processing left member: {e}")
        await session.rollback()


    return False

async def proccess_new_member(new_member: User, chat:TelegramChat, session:AsyncSession) -> Tuple[TelegramUser, UserChatAssociation]:
    user_id = new_member.id
    username = new_member.username
    user = await get_or_create_user(session, user_id, username)

    association_record = await get_or_create_association(
        session,
        user_id,
        chat.telegram_id,
        constants.UserRole.MEMBER,
    )
    return user, association_record







# 

async def mute_user(session: AsyncSession, 
                    duration: DurationString,
                    reason: Optional[str] = "Bad word",
                    muted_by: Optional[TelegramUser] = None,
                    user_id: Optional[int] = None,
                    chat_id: Optional[int] = None):
    if isinstance(duration, str): duration = DurationString(duration)

    stmt = update(UserChatAssociation).\
        where(UserChatAssociation.user_id == user_id).\
        where(UserChatAssociation.chat_id == chat_id).\
        values(
            mute_expires=duration.to_datetime(),
            mute_metadata={
                "reason": reason,
                "time": to_timestamp(utcnow()),
                "by": muted_by.id if muted_by else 'system'
            },
            warn_count = 0
        )

    await session.execute(stmt)
    await session.commit()
    return True


async def ban_user(session: AsyncSession, 
                  duration: DurationString,
                  user_id: int,
                  chat_id: int,
                  reason: Optional[str] = "Offtop",
                  banned_by: Optional[TelegramUser] = None):
    if isinstance(duration, str): duration = DurationString(duration)

    stmt = update(UserChatAssociation).\
    where(UserChatAssociation.user_id == user_id).\
    where(UserChatAssociation.chat_id == chat_id).\
    values(
        ban_expires=duration.to_datetime(),
        ban_metadata={
            "reason": reason,
            "time": to_timestamp(utcnow()),
            "by": banned_by.id if banned_by else 'system'
        }
    )

    await session.execute(stmt)
    await session.commit()
    return True


async def warn_user(session: AsyncSession,
                    reason: str, 
                    user_id: int,
                    chat_id: int,
                    warned_by: Optional[TelegramUser] = None,
                    current_warn_count: Optional[int] = None) -> Tuple[bool, bool]:
    if current_warn_count and current_warn_count + 1 >= 3:
        mute_result =await mute_user(
            session, DurationString("1h"),
            reason=reason,
            user_id=user_id,
            chat_id=chat_id,
            muted_by=warned_by
        )
        return True, mute_result


    stmt = update(UserChatAssociation).\
        where(UserChatAssociation.user_id == user_id).\
        where(UserChatAssociation.chat_id == chat_id).\
        values(
            warn_count=func.coalesce(UserChatAssociation.warn_count, 0) + 1 
        )

    await session.execute(stmt)
    await session.commit()
    return True, False





def is_message_safe(chat_settings:ChatSettings, text: str) -> Tuple[bool, Optional[Literal["bad-word", "bad-link"]]]:
    if not chat_settings.moderation.enabled:
        return True, ""
    
    if not text:
        return True, ""


    if chat_settings.restricted_words.enabled:
        if chat_settings.restricted_words.words and text:
            if  any(bad_word in text for bad_word in chat_settings.restricted_words.words):
                return False, "bad-word"
        
        is_toxic, max_similarity, toxic_match = is_toxic_message(text)
        if is_toxic:
            return False, f"bad-word: {toxic_match} ({max_similarity})"
    
    if chat_settings.link_filtering.enabled:
        urls = extract_urls(text)
        # print((urls, chat_settings.link_filtering))
        
        if chat_settings.link_filtering.block_all and urls:
            return False, "bad-link"
        
        whitelist = chat_settings.link_filtering.whitelist
        for url in urls:
            if not any(allowed_url in url for allowed_url in whitelist):
                return False, "bad-link"
            
    return True, ""


async def punish_user(
    session: AsyncSession, 
    user: TelegramUser,
    chat: TelegramChat,
    association: UserChatAssociation,
) -> Tuple[TelegramUser, TelegramChat, UserChatAssociation]:
    chat_settings = chat.settings
    warning_threshold = chat_settings.restricted_words.punishment.warning_threshold
    warn_count = association.warn_count

    if warn_count >= warning_threshold and warning_threshold > 0:
        association.mute_expires = chat_settings.restricted_words.punishment.duration.to_datetime()
        association.mute_metadata = {
            "reason": "Використання заборонених слів",
            "time": to_timestamp(utcnow()),
            "by": "system"
        }
        association.warn_count = 0
    elif warn_count < warning_threshold:
        association.warn_count += 1
    
    await session.commit()

    return user, chat, association