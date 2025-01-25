import asyncio
from datetime import timedelta
import random
from aiogram import types
from app import commands, services
from app.classes import DurationString
from app.schemas import TelegramUserPermissions 
from app import strings
from app import constants
from app.dependencies import with_session, with_user_and_chat_and_rights, with_user_rights
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.models import TelegramChat, TelegramUser, UserChatAssociation
from app.schemas import BotUserState
from app.utils import encode_inline_data, format_timedelta_ua, format_timedelta_uk, get_chat_members, get_random_cat_gif, parse_command_args, parse_mute_command, subtract_datetimes, utcnow
from app.cache import set_chat_state, set_user_state

@with_user_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
@with_session
async def on_init_command(message: types.Message, session: AsyncSession):
    chat_id = message.chat.id
    chat_type = constants.ChatType(message.chat.type)
    if chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)
        
    
    chat_title = message.chat.title if message.chat.title else message.chat.full_name
    chat_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
    
    if not isinstance(chat_member, (types.ChatMemberOwner, types.ChatMemberAdministrator)):
        await message.reply(strings.NO_RIGHTS)
        return
    
    user_role = None
    if isinstance(chat_member, types.ChatMemberOwner):
        user_role = constants.UserRole.OWNER
    elif isinstance(chat_member, types.ChatMemberAdministrator):
        user_role = constants.UserRole.ADMIN

    
    chat = await services.get_or_create_chat(session, chat_id, chat_title, chat_type)




    if chat and chat.id and chat_type in [constants.ChatType.SUPERGROUP, constants.ChatType.CHANNEL]:
        last_init = chat.last_init
        if last_init:
            time_since_last_init = subtract_datetimes(utcnow(), last_init)
            if time_since_last_init < constants.INIT_CMD_COOLDOWN_TIME:
                remaining_time = constants.INIT_CMD_COOLDOWN_TIME - time_since_last_init
                await message.reply(strings.ACTION_NOT_ALLOWED_TIMER.format(time=format_timedelta_uk(remaining_time)))
                return
        
        

        init_message = await message.bot.send_message(
            chat_id,
            strings.BOT_INIT_START_SETUP,
            reply_to_message_id=message.message_id,
            message_thread_id=message.message_thread_id
        )
    


        users = await get_chat_members(chat_id)
        admins = await message.bot.get_chat_administrators(chat_id)
        admin_ids = [(admin.user.id, admin.user.username, TelegramUserPermissions.from_user(admin)) for admin in admins if not admin.user.is_bot]

        for admin_id, admin_username, admin_permission in admin_ids:
            admin_user = await services.get_or_create_user(session, admin_id, username=admin_username)
            association = await services.get_or_create_association(
                session, admin_id, chat_id, user_role,
                privileges=admin_permission
            )

        admin_ids_set = {admin_id for admin_id, _, _ in admin_ids}
        members = [user for user in users if user[1] not in admin_ids_set]
        
        
        for member_username, member_id, member_permission in members:
            user = await services.get_or_create_user(session, member_id, username=member_username)
            association = await services.get_or_create_association(
                session, member_id, chat_id, constants.UserRole.MEMBER,
                privileges=member_permission
            )


        chat.last_init = utcnow()
        session.add(chat)
        await session.commit()

        await message.bot.edit_message_text(
            strings.BOT_INIT_SUCCESS,
            chat_id=chat_id,
            message_id=init_message.message_id,
        )
    else:
        await message.reply(strings.ACTION_NOT_ALLOWED)

@with_user_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
@with_session
async def on_my_chats_command(message: types.Message, session:AsyncSession):
    chat_type = constants.ChatType(message.chat.type)
    if chat_type != constants.ChatType.PRIVATE:
        await message.reply(strings.ONLY_IN_PRIVATE)
        return
    
    user_id = message.from_user.id
    # username =  message.from_user.username
    user = await services.get_user_by(session, user_id)
    chats = await services.get_user_chats(session, user)
    if not chats:
        await message.reply(strings.CHATS_NOT_FOUND)
        return
    
    kb = InlineKeyboardBuilder()
    for chat in chats:
        kb.button(text=chat.title, callback_data=encode_inline_data("chat-edit-menu", "chat", chat.telegram_id))
        await set_chat_state(chat.telegram_id, chat)

    new_message =  await message.reply(strings.BOT_YOUR_CHATS, reply_markup=kb.as_markup())
    state = BotUserState(
        user_id=message.from_user.id,
        last_message_id=new_message.message_id
    )
    await set_user_state(user_id, state)
    return new_message


# @with_user_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_mute_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)
    
    duration, reason = parse_mute_command(message.text)
    if not message.reply_to_message:
        return await message.reply(strings.COMMAND_NO_REPLY)
    
    if message.reply_to_message.from_user.is_bot: return await message.delete()


    if not duration or not reason:
        return await message.reply(strings.MUTE_COMMAND_INVALID_FORMAT)
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    muted_user = await services.get_or_create_user(
        session, user_id, username
    )
    muted_user_association = muted_user.get_association(chat_id)

    if muted_user_association.role == constants.UserRole.ADMIN:
        if association.role != constants.UserRole.OWNER:
            return await message.reply(strings.MUTE_COMMAND_ADMIN_CANNOT_MUTE)

    if muted_user_association.role == constants.UserRole.OWNER:
        if association.role == constants.UserRole.OWNER:
            duration = duration.limit_timedelta(timedelta(minutes=30))


    result = await services.mute_user(
        session, duration, 
        user_id = user_id,
        chat_id = chat_id,
        reason=reason, 
        muted_by=user,
    )    

    if chat.chat_type is constants.ChatType.SUPERGROUP:
        if muted_user_association.role != constants.UserRole.OWNER:
            res = await message.bot.restrict_chat_member(
                chat_id=chat.telegram_id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=False),
                until_date=duration.to_datetime()
            )

    return await message.reply(
        strings.MUTE_COMMAND_SUCCESS_ADMIN.format(
            username=username,
            duration=format_timedelta_ua(duration.to_timedelta()),
            reason=reason
        )
    )


@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_unmute_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)  
    

    if not message.reply_to_message:
        return await message.reply(strings.COMMAND_NO_REPLY)
    
    if message.reply_to_message.from_user.is_bot: return await message.delete()
    
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    muted_user = await services.get_or_create_user(
        session, user_id, username
    )
    muted_user_association:UserChatAssociation = muted_user.get_association(chat_id)


    if not muted_user_association or not muted_user_association.mute_expires:
        return await message.reply(strings.USER_NOT_MUTED)
    
    muted_user_association.mute_expires = None
    muted_user_association.mute_metadata = {}
    session.add(muted_user_association)
    await session.commit()
    
    if chat.chat_type is constants.ChatType.SUPERGROUP:
        if muted_user_association.role != constants.UserRole.OWNER:
            res = await message.bot.restrict_chat_member(
                chat_id=chat.telegram_id,
                user_id=user_id,
                permissions=types.ChatPermissions(can_send_messages=True),
                until_date=None
            )


    return await message.reply(
        strings.UNMUTE_COMMAND_SUCCESS.format(username=username)
    )

@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_ban_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)  

    if not message.reply_to_message:
        return await message.reply(strings.COMMAND_NO_REPLY)
    
    if message.reply_to_message.from_user.is_bot: return await message.delete()

    args, error = parse_command_args(message.text, [DurationString, str])
    if error:
        return await message.reply(error)

    duration, reason = args
    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    banned_user = await services.get_or_create_user(
        session, user_id, username
    )
    banned_user_association:UserChatAssociation = banned_user.get_association(chat_id)
    if banned_user_association.role == constants.UserRole.ADMIN:
        if association.role != constants.UserRole.OWNER:
            return await message.reply(strings.BAN_COMMAND_ADMIN_CANNOT_BAN)

    if banned_user_association.role == constants.UserRole.OWNER:
        if association.role == constants.UserRole.OWNER:
            duration = duration.limit_timedelta(timedelta(minutes=30))

    print(banned_user)
    print(user)
    print(banned_user_association)

    # return

    result = await services.ban_user(
        session, duration, 
        user_id = user_id,
        chat_id = chat_id,
        reason=reason, 
        banned_by=user,
    )    


    if chat.chat_type is constants.ChatType.SUPERGROUP:
        if banned_user_association.role != constants.UserRole.OWNER:
            res = await message.bot.ban_chat_member(
                chat_id=chat.telegram_id,
                user_id=user_id,
                until_date=duration.to_datetime()
            )

    return await message.reply(
        strings.MUTE_COMMAND_SUCCESS_ADMIN.format(
            username=username,
            duration=format_timedelta_ua(duration.to_timedelta()),
            reason=reason
        )
    )


@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_unban_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)  


    # args, error = commands.UNBAN_COMMAND_PARSER(message.text)
    # if error:
    #     return await message.reply(error)
    
    if not message.reply_to_message and not username:
        return await message.reply(strings.COMMAND_NO_REPLY)
    
    if message.reply_to_message.from_user.is_bot: return await message.delete()

    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    banned_user = await services.get_or_create_user(
        session, user_id, username
    )
    banned_user_association:UserChatAssociation = banned_user.get_association(chat_id)

    # if not banned_user_association or not banned_user_association.ban_expires:
    #     return await message.reply(strings.USER_NOT_BANNED)
    
    banned_user_association.ban_expires = None
    banned_user_association.ban_metadata = {}
    session.add(banned_user_association)
    await session.commit()
    
    if chat.chat_type is constants.ChatType.SUPERGROUP:
        if banned_user_association.role != constants.UserRole.OWNER:
            res = await message.bot.unban_chat_member(
                chat_id=chat.telegram_id,
                user_id=user_id,
                only_if_banned=True
            )

    return await message.reply(
        strings.UNBAN_COMMAND_SUCCESS.format(username=username)
    )


@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_warn_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)  

    if not message.reply_to_message:
        return await message.reply(strings.COMMAND_NO_REPLY)

    args, error = commands.WARN_COMMAND_PARSER(message.text)
    if error:
        return await message.reply(error)
    
    reason = args.get('reason')
    username = args.get('username')

    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    warned_user = await services.get_or_create_user(
        session, user_id, username
    )
    warned_user_association:UserChatAssociation = warned_user.get_association(chat_id)
    warn_result, mute_result = await services.warn_user(
        session, reason,
        user_id = user_id,
        chat_id = chat_id,
        warned_by=user,
        current_warn_count = warned_user_association.warn_count
    )   
    await session.refresh(warned_user_association)
    if mute_result:
        return await message.reply(
            strings.MUTE_COMMAND_SUCCESS_ADMIN.format(
                username=username,
                duration=format_timedelta_ua(DurationString('1h').to_timedelta()),
                reason=reason
            )
        )

    return await message.reply(
        strings.WARN_COMMAND_SUCCESS_ADMIN.format(
            username=username,
            reason=reason,
            warn_count = association.warn_count
        )
    )


@with_user_and_chat_and_rights(required_role=[constants.UserRole.ADMIN, constants.UserRole.OWNER])
async def on_bot_unwarn_command(message: types.Message, 
                     session: AsyncSession, user: TelegramUser, chat: TelegramChat, association: UserChatAssociation):
    if chat.chat_type.is_private:
        return await message.reply(strings.ONLY_IN_GROUP)  

    if not message.reply_to_message:
        return await message.reply(strings.COMMAND_NO_REPLY)

    if message.reply_to_message.from_user.is_bot: return await message.delete()
    # args, error = commands.WARN_COMMAND_PARSER(message.text)
    # if error:
    #     return await message.reply(error)

    chat_id = message.chat.id
    user_id = message.reply_to_message.from_user.id
    username = message.reply_to_message.from_user.username
    warned_user = await services.get_or_create_user(
        session, user_id, username
    )
    warned_user_association:UserChatAssociation = warned_user.get_association(chat_id)

    if not warned_user_association or warned_user_association.warn_count == 0:
        return await message.reply(strings.USER_NOT_WARNED)
    
    warned_user_association.warn_count = warned_user_association.warn_count - 1
    session.add(warned_user_association)
    await session.commit()
    await session.refresh(warned_user_association)

    return await message.reply(
        strings.UNWARN_COMMAND_SUCCESS.format(username=username)
    )


async def on_bot_dice_command(message: types.Message):
    await message.answer_dice(
        reply_to_message_id=message.message_thread_id
    )
    return await message.delete()
    

async def on_cat_gif_command(message: types.Message):
    gif_url = await get_random_cat_gif()
    if gif_url:
        return await message.reply_video(gif_url)
        return await message.reply(git_url)
    
async def on_bot_coin_command(message: types.Message):
    msg = await message.answer("🪙 Кидаю монету...")
    await message.delete()
    await asyncio.sleep(random.uniform(0.5, 2))
    coin_flip = "Орел" if random.choice([True, False]) else "Решка"
    await msg.edit_text(f"🪙 Випало число: {coin_flip}")