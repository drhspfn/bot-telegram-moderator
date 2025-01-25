
from functools import wraps
from typing import Any, Callable, List, cast
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from app.cache import check_user_spam_status, increment_user_message_count
from app.database import get_session
from app.services import get_or_create_association, get_or_create_user, get_or_create_chat
from app import constants, strings
from app.utils import check_admin_rights, format_timedelta_uk, subtract_datetimes, utcnow

def with_session(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    async def wrapper(*args: tuple, **kwargs: dict) -> Any:
        async with get_session() as session:
            return await func(*args, session=session, **kwargs)
    return wrapper

def with_user_rights(required_rights: List[constants.Permission] = None, required_role: List[constants.UserRole] = None):
    def decorator(func) -> Any:
        @wraps(func)
        async def wrapper(message: types.Message, *args, **kwargs):
            if message.chat.type != 'private':
                result = await message.bot.get_chat_member(
                    message.chat.id,
                    message.from_user.id,
                )
                user_role = constants.UserRole.MEMBER 
                if isinstance(result, types.ChatMemberOwner):
                    user_role = constants.UserRole.OWNER 
                elif isinstance(result, types.ChatMemberAdministrator):
                    user_role = constants.UserRole.ADMIN 
                elif isinstance(result, types.ChatMemberMember):
                    user_role = constants.UserRole.MEMBER 
                elif isinstance(result, types.ChatMemberBanned):
                    user_role = constants.UserRole.BANNED

                if (required_rights or required_role):
                    has_rights = check_admin_rights(user_role, required_rights, required_role)
                    if not has_rights:
                        return await message.answer("You do not have the required permissions.")
            return await func(message, *args, **kwargs)
        return wrapper
    return decorator

def with_user_and_chat_and_rights(required_rights: List[constants.Permission] = None, required_role: constants.UserRole = None):
    def decorator(func) -> Any:
        @wraps(func)
        async def wrapper(message: types.Message, *args, **kwargs):
            async with get_session() as session:
                session = cast(AsyncSession, session)
                if message.from_user.is_bot: return
                chat_type = constants.ChatType(message.chat.type)
                chat_title = message.from_user.full_name if chat_type.is_private else message.chat.title

                user = await get_or_create_user(
                    session,
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                )

                chat = await get_or_create_chat(
                    session,
                    telegram_id=message.chat.id,
                    title=chat_title,
                    chat_type=chat_type
                )
                association = None

                if chat_type != constants.ChatType.PRIVATE:
                    association = await get_or_create_association(
                        session,
                        user_id=user.telegram_id,
                        chat_id=chat.telegram_id,
                    )

                    if association.mute_expires or  association.ban_expires:
                        now = utcnow()
                        if association.mute_expires:
                            message_content = strings.ALREADY_MUTED.format(time_left = format_timedelta_uk(subtract_datetimes(association.mute_expires, now)))
                        elif association.ban_expires:
                            message_content = strings.ALREADY_BANNED.format(time_left = format_timedelta_uk(subtract_datetimes(association.ban_expires, now)))


                        await message.delete()
                        if await check_user_spam_status(chat.telegram_id, user.telegram_id):
                            return
                        
                        await increment_user_message_count(chat.telegram_id, user.telegram_id)
                        return await message.bot.send_message(
                            chat.telegram_id,
                            message_content,
                            message_thread_id=chat.settings_notify_system_thread_id
                        )


                    if (required_rights or required_role) and association:
                        has_rights = check_admin_rights(association.role, required_rights, required_role)
                        if not has_rights:
                            return await message.answer("You do not have the required permissions.")

                return await func(message, session, user, chat, association, *args, **kwargs)
        return wrapper
    return decorator
