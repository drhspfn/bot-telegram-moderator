from typing import Optional, cast
from aiogram import types
from app import services
from app import strings
from app import schemas
from app import constants
from app.cache import get_user_state, check_user_spam_status, increment_user_message_count, set_user_state
from app.classes import DurationString
from app.dependencies import with_session, with_user_and_chat_and_rights
from sqlalchemy.ext.asyncio import AsyncSession
from .inline import show_ban_words_edit, show_ban_links_whitelist_edit
from app.models import TelegramUser, TelegramChat, UserChatAssociation
from app.utils import compare_links, encode_inline_data, format_timedelta_ua, is_link, subtract_datetimes, utcnow
from aiogram.utils.keyboard import InlineKeyboardBuilder



@with_session
async def on_left_chat_member(message: types.ChatMemberUpdated, session:AsyncSession):
    if message.new_chat_member and message.new_chat_member.status in ["kicked"]:
        if message.new_chat_member.user.is_bot: 
            return
        chat_id = message.chat.id
        chat_type = constants.ChatType(message.chat.type)
        chat_title = message.from_user.full_name if chat_type.is_private else message.chat.title

        chat = await services.get_or_create_chat(session, chat_id, chat_title, chat_type)
        left_user_id = message.new_chat_member.user.id
        association = await services.get_association(session, left_user_id, chat_id)
        
        if association and association.ban_expires: 
            return
        if isinstance(message.new_chat_member, types.ChatMemberBanned): 
            return
        
        await services.proccess_left_member(left_user_id, chat_id, session)

        if chat.settings.notifications.left_user_notifications:
            thread_id = chat.settings.notifications.new_user_thread_id or chat.settings.notifications.system_thread_id or None
            await message.bot.send_message(chat_id, strings.USER_FAREWELL.format(username=message.new_chat_member.user.username),
                                            message_thread_id=thread_id)

@with_session
async def on_new_chat_member(message: types.ChatMemberUpdated, session:AsyncSession):
    if message.chat.type == "private": return
    if message.new_chat_member and message.new_chat_member.status == "member":
        chat_id = message.chat.id
        chat_type = constants.ChatType(message.chat.type)
        chat_title = message.from_user.full_name if chat_type.is_private else message.chat.title

        chat = await services.get_or_create_chat(session, chat_id, chat_title, chat_type)

        if message.new_chat_member.user.is_bot: return
        user, user_association = await services.proccess_new_member(message.new_chat_member.user, chat, session)

        if user_association.ban_expires:
            await message.bot.ban_chat_member(
                chat_id=chat.telegram_id,
                user_id=user.telegram_id,
                until_date=user_association.ban_expires
            )
            await message.bot.send_message(
                chat_id,
                strings.USER_BANNED_MESSAGE.format(
                    username=user.username
                ),
            )
            return 


        await message.bot.restrict_chat_member(
            chat_id,
            user.telegram_id,
            types.ChatPermissions(
                can_send_messages=False
            )
        )

        kb = InlineKeyboardBuilder()
        kb.button(
            text=strings.WELCOME_RULES_ACCEPT, 
            callback_data=encode_inline_data("welcome", "rules-accept", user.telegram_id)
        )
        thread_id = chat.settings.notifications.new_user_thread_id or chat.settings.notifications.system_thread_id or None
        user_state = await get_user_state(user.telegram_id)
        user_state.read_rules_start = utcnow()
        await set_user_state(user.telegram_id, user_state)
        return await message.answer(strings.NEW_USER_WELCOME_RULES.format(
            username=user.username,
            rules_url="example-rules.com" # TODO: chat.settings.moderation.read_rules.url
        ), message_thread_id=thread_id, reply_markup=kb.as_markup())
        

        

        # if chat.settings.notifications.new_user_notifications:
        #     thread_id = chat.settings.notifications.new_user_thread_id or chat.settings.notifications.system_thread_id or None
        #     await message.bot.send_message(chat_id, strings.NEW_USER_WELCOME.format(username=user.username),
        #                                     message_thread_id=thread_id)




@with_session
async def on_user_permissions_changed(event: types.ChatMemberUpdated, session:AsyncSession):
    # return print(event.new_chat_member)
    user_id = event.new_chat_member.user.id
    chat_id = event.chat.id
    # username = event.new_chat_member.user.username
    # old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    new_permissions = schemas.TelegramUserPermissions.from_user(event.new_chat_member)
    new_permissions.is_member = True
    

    user = await services.get_user_by(session, user_id)
    association = user.get_association(chat_id)
    association = cast(Optional[UserChatAssociation], association)
    if not association:
        # TODO: I don't know what it is or why, if I figure it out, we'll do it, but maybe it's not necessary.
        return 
    

    association._privileges = new_permissions.model_dump(mode="json")
    association.role = {
        "administrator": constants.UserRole.ADMIN,
        "member": constants.UserRole.MEMBER,
        "restricted": constants.UserRole.MEMBER,
    }.get(new_status)

    await session.commit()
    return


@with_session
async def on_rm_duration_message(message: types.Message, session:AsyncSession):
    chat_type = constants.ChatType(message.chat.type)
    if chat_type != constants.ChatType.PRIVATE:
        await message.reply(strings.ONLY_IN_PRIVATE)
        return
    
    user_id = message.from_user.id
    user_state = await get_user_state(user_id)
    if not user_state: return await message.delete()

    if user_state.state != constants.UserState.EDIT_BOT_RESTRICTED_WORD_DURATION: return await message.delete()

    try:
        chat_state = await services.get_chat_from_cache(user_state.edit.selected_chat_tid)
        punishment_type = {
            'ban': strings.BAN,
            "mute": strings.MUTE
        }.get(chat_state.settings.restricted_words.punishment.type)

        chat_settings = chat_state.settings.model_copy()
        chat_settings.restricted_words.punishment.duration = DurationString(message.text)
        await services.update_chat_settings_by_id(session, user_state.edit.selected_chat_tid, chat_settings)
        kb = InlineKeyboardBuilder()
        kb.button(
            text=strings.OFF if chat_settings.restricted_words.enabled else strings.ON, 
            callback_data=encode_inline_data("chat-edit", "toggle-bn-enabled", "-")
        ) 
        kb.button(
            text=f"{strings.PUNISHENT}: {punishment_type}", 
            callback_data=encode_inline_data("chat-edit", "toggle-bn-punishment-type")
        )
        kb.button(
            text=f"{strings.PUNISHENT_DURATION}: {chat_settings.restricted_words.punishment.duration}", 
            callback_data=encode_inline_data("chat-edit", "toggle-bn-punishment-time")
        )
        kb.button(
            text=strings.BACK, 
            callback_data=encode_inline_data("chat-edit", "edit", message.chat.id)
        )
        kb.adjust(1) 

        user_state.state = None
        await show_ban_words_edit(message, user_state)
        return await message.delete()
    except Exception as e:
        ...
 
# @with_session
async def on_link_filter_whitelist_add(message: types.Message, session:AsyncSession):
    if not is_link(message.text):
        await message.answer(strings.INVALID_LINK)
        return await message.delete()
    

    user_state = await get_user_state(message.from_user.id)
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    if compare_links(message.text, chat_settings.link_filtering.whitelist):
        await message.reply(strings.LINK_ALREADY_IN_WHITELIST)
        return await message.delete()
    

    chat_settings.link_filtering.whitelist.append(message.text)
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    return await show_ban_links_whitelist_edit(message, user_state)

# @with_session
async def on_link_filter_whitelist_delete(message: types.Message, session:AsyncSession):
    if not is_link(message.text):
        await message.reply(strings.INVALID_LINK)
        return await message.delete()
    
    user_state = await get_user_state(message.from_user.id)
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    if not compare_links(message.text, chat_settings.link_filtering.whitelist):
        await message.reply(strings.LINK_NOT_IN_WHITELIST)
        return await message.delete()
    
    chat_settings.link_filtering.whitelist.remove(message.text)
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    return await show_ban_links_whitelist_edit(message, user_state)

@with_user_and_chat_and_rights()
async def on_global_message(
    message:types.Message,
    session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation
):
    if message.chat.type == "private": 
        user_state = await get_user_state(message.from_user.id)
        if user_state:
            if user_state.state is constants.UserState.EDIT_BOT_LINK_FILTER_ADD:
                return await on_link_filter_whitelist_add(message, session)
            elif user_state.state is constants.UserState.EDIT_BOT_LINK_FILTER_DELETE:
                return await on_link_filter_whitelist_delete(message, session)
        return
    

    if not chat.settings and association.role in [constants.UserRole.ADMIN, constants.UserRole.OWNER]: 
        return await message.reply(strings.CHAT_NOT_CONFIGURED)

    now = utcnow()
    is_safe, reason = services.is_message_safe(chat.settings, message.text)
    if not is_safe:
        chat_id = message.chat.id
        await message.delete()


        user, chat, association = await services.punish_user(
            session, user, chat, association
        )

        punishment_message = ""
        if association.warn_count > 0:
            punishment_message = strings.RESTRICTED_WORD_WARNING.format(
                current_warn_count = association.warn_count,
                max_warn_count = chat.settings.restricted_words.punishment.warning_threshold,
                punishment_type = strings.punish_type(chat.settings.restricted_words.punishment.type)
            )
        elif association.mute_expires:
            punishment_message = strings.MUTED_WARNING.format(time_left = format_timedelta_ua(subtract_datetimes(association.mute_expires, now)))
            if chat.chat_type is constants.ChatType.SUPERGROUP and not association.role in [constants.UserRole.OWNER, constants.UserRole.ADMIN]:
                await message.bot.restrict_chat_member(
                    chat_id=chat.telegram_id,
                    user_id=user.telegram_id,
                    permissions=types.ChatPermissions(can_send_messages=False),
                    until_date=association.mute_expires
                )
        elif association.ban_expires:
            punishment_message = strings.BANNED_WARNING.format(time_left = format_timedelta_ua(subtract_datetimes(association.mute_expires, now)))
            if chat.chat_type in [constants.ChatType.SUPERGROUP,constants.ChatType.GROUP, constants.ChatType.CHANNEL] \
                    and not association.role in [constants.UserRole.OWNER, constants.UserRole.ADMIN]:
                await  message.bot.ban_chat_member(
                    chat=chat.telegram_id,
                    user_id=user.telegram_id,
                    until_date=association.ban_expires
                )
        if punishment_message:
            if await check_user_spam_status(chat_id, user.telegram_id):
                return
            
            await message.bot.send_message(
                chat_id=chat_id,
                text=punishment_message,
                message_thread_id=message.message_thread_id
            )
            await increment_user_message_count(chat_id, user.telegram_id)