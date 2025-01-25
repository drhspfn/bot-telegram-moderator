from datetime import timedelta
from typing import Union
from aiogram import types
from app import services
from app import strings
from app import constants
from app.dependencies import with_session, with_user_and_chat_and_rights
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import TelegramUser, TelegramChat, UserChatAssociation
from app.schemas import BotUserState, BotUserStateEdit
from app.utils import decode_inline_data, encode_inline_data, format_timedelta_uk, utcnow
from app.cache import get_user_state, set_user_state
from aiogram.utils.keyboard import InlineKeyboardBuilder


@with_session
async def on_edit_chat_menu(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    prefix, sub_prefix, raw_data = decode_inline_data(callback.data)
    print((prefix, sub_prefix, raw_data))
    user_state = await get_user_state(user_id)
    if not user_state: 
        await callback.answer("Помилка даних, почніть з початку...", show_alert=True)
        return await callback.message.delete()


    if sub_prefix == "chat":
        return await show_chat_details(callback, session, raw_data, user_id)
    elif sub_prefix == "exit":
        await callback.message.delete()

@with_session
async def on_edit_chat_settings(callback: types.CallbackQuery, session: AsyncSession):
    prefix, sub_prefix, raw_data = decode_inline_data(callback.data)
    print((prefix, sub_prefix, raw_data))
    user_id = callback.from_user.id
    user_state = await get_user_state(user_id)
    if not user_state: 
        await callback.answer("Помилка даних, почніть з початку...", show_alert=True)
        return await callback.message.delete()



    if sub_prefix == "edit":
        await show_edit_menu(callback, user_state)
    elif sub_prefix == "edit-basic":
        await show_basic_edit(callback, user_state)
    elif sub_prefix == "toggle-basic-enabled":
        await toggle_basic_enabled(callback, session, user_state)
    elif sub_prefix == "edit-welcome-rules":
        await show_welcome_rules(callback, user_state)
    elif sub_prefix == "edit-notify":
        await show_notify_edit(callback, user_state)

    ##### Ban words
    elif sub_prefix == "edit-banwords":
        await show_ban_words_edit(callback, user_state)
    elif sub_prefix == "toggle-bw-enabled":
        await toggle_bw_enabled(callback, session, user_state)
    elif sub_prefix == "toggle-bw-punishment-type":
        await toggle_ban_words_punishment_type(callback, session, user_state, raw_data)
    elif sub_prefix == "toggle-bw-punishment-time":
        await toggle_ban_words_punishment_time(callback, session, user_state, raw_data)

    ##### Ban links
    elif sub_prefix == "edit-banlinks":
        await show_ban_links_edit(callback, user_state)
    elif sub_prefix == "toggle-lf-enabled":
        await toggle_ban_links_enabled(callback, session, user_state)
    elif sub_prefix == "toggle-lf-blockall":
        await toggle_ban_links_blockall(callback, session, user_state)
    elif sub_prefix == "edit-lf-whitelist":
        await show_ban_links_whitelist_edit(callback, user_state)
    elif sub_prefix == "add-lf-whitelist":
        await show_ban_links_whitelist_add(callback, user_state)
    elif sub_prefix == "delete-lf-whitelist":
        await show_ban_links_whitelist_delete(callback, user_state)

    
    


### Функції для спрощення коду з Callback
async def show_chat_details(callback: types.CallbackQuery, session: AsyncSession, raw_data: str, user_id: int):
    chat_data = await services.get_chat_by(session, int(raw_data))
    user_state = await get_user_state(callback.from_user.id)
    user_state.edit = BotUserStateEdit(
        user_id =callback.from_user.id,
        selected_chat_id=chat_data.id,
        selected_chat_tid=chat_data.telegram_id,
        settings=chat_data.settings
    )
    user_state.last_inline_message_id=callback.inline_message_id
    await set_user_state(user_id, user_state)
    
    kb = InlineKeyboardBuilder()
    kb.button(text=strings.EDIT, callback_data=encode_inline_data("chat-edit", "edit", chat_data.telegram_id))
    kb.row(types.InlineKeyboardButton(text=strings.BACK, callback_data=encode_inline_data("chat-edit-menu", "exit", "")))
    kb.adjust(2)

    await callback.message.edit_text(strings.BOT_CHATS_DETAILS.format(
        chat_title=chat_data.title,
        chat_type=chat_data.chat_type.to_locale,
        chat_id=chat_data.telegram_id,
        chat_user_count=len(chat_data.users)
    ), reply_markup=kb.as_markup())

    
async def toggle_basic_enabled(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    chat_settings.moderation.enabled = not chat_settings.moderation.enabled
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    await show_basic_edit(callback, user_state)

async def toggle_bw_enabled(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    chat_settings.restricted_words.enabled = not chat_settings.restricted_words.enabled
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    await show_ban_words_edit(callback, user_state)

async def show_edit_menu(callback: types.CallbackQuery, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    kb = InlineKeyboardBuilder()
    kb.button(text=strings.EDIT_BASIC, callback_data=encode_inline_data("chat-edit", "edit-basic", chat_id))
    kb.button(text=strings.EDIT_NOTIFY, callback_data=encode_inline_data("chat-edit", "edit-notify", chat_id))
    kb.button(text=strings.EDIT_BAN_WORDS, callback_data=encode_inline_data("chat-edit", "edit-banwords", chat_id))
    kb.button(text=strings.EDIT_BAN_LINKS, callback_data=encode_inline_data("chat-edit", "edit-banlinks", chat_id))
    kb.row()
    kb.add(types.InlineKeyboardButton(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "chat", chat_id)))
    kb.adjust(2)

    await callback.message.edit_text(strings.BOT_EDIT_CHAT_MOD_SETTINGS, reply_markup=kb.as_markup())

async def show_basic_edit(callback: types.CallbackQuery, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    
    kb = InlineKeyboardBuilder()
    kb.button(
        text=strings.OFF if chat_settings.moderation.enabled else strings.ON, 
        callback_data=encode_inline_data("chat-edit", "toggle-basic-enabled", "-")
    )
    kb.button(
        text=strings.RULES_ON_WELCOME, 
        callback_data=encode_inline_data("chat-edit", "edit-welcome-rules", "-")
    )
    kb.button(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "edit", chat_id))
    kb.adjust(1)
    await callback.message.edit_text(strings.CHAT_EDIT_BASIC.format(
        is_mod_on=strings.YES if chat_settings.moderation.enabled else strings.NO
    ), reply_markup=kb.as_markup())

async def show_welcome_rules(callback: types.CallbackQuery, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    kb = InlineKeyboardBuilder()
    kb.button(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "edit", chat_id))

    await callback.message.edit_text(strings.CHAT_RULES_SETTINGS.format(
        is_rules_enabled=strings.yes_no(chat_settings.moderation.read_rules.enabled),
        rules_link=chat_settings.moderation.read_rules.url
    ), reply_markup=kb.as_markup())



async def show_notify_edit(callback: types.CallbackQuery, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    kb = InlineKeyboardBuilder()
    kb.button(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "edit", chat_id))

    await callback.message.edit_text(strings.CHAT_EDIT_NOTIFY.format(
        is_new_member_on=strings.YES if chat_settings.notifications.new_user_notifications else strings.NO
    ), reply_markup=kb.as_markup())

async def show_ban_links_edit(callback: types.CallbackQuery, user_state: BotUserState) -> None:
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"{strings.ENABLED}: {strings.yes_no(chat_settings.link_filtering.enabled)}", 
        callback_data=encode_inline_data("chat-edit", "toggle-lf-enabled", "-")
    )
    kb.button(
        text=f"{strings.BLOCK_ALL}: {strings.yes_no(chat_settings.link_filtering.block_all)}", 
        callback_data=encode_inline_data("chat-edit", "toggle-lf-blockall", "-")
    )
    kb.button(
        text=strings.WHITE_LIST, 
        callback_data=encode_inline_data("chat-edit", "edit-lf-whitelist", "-")
    )
    kb.button(
        text=strings.BACK, 
        callback_data=encode_inline_data("chat-edit", "edit", chat_id)
    )
    kb.adjust(1) 
    await callback.message.edit_text(
        strings.CHAT_EDIT_RESTRICTED_LINKS.format(
            is_mod_on = strings.yes_no(chat_settings.link_filtering.enabled),
            ban_all_links = strings.yes_no(chat_settings.link_filtering.block_all),
            whitelist_label = ", ".join(chat_settings.link_filtering.whitelist)
        ), 
        reply_markup=kb.as_markup()
    )
    
async def toggle_ban_links_enabled(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    chat_settings.link_filtering.enabled = not chat_settings.link_filtering.enabled
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    return await show_ban_links_edit(callback, user_state)

async def show_ban_links_whitelist_delete(
        callback: types.CallbackQuery,
        user_state: BotUserState
):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    user_state.state = constants.UserState.EDIT_BOT_LINK_FILTER_DELETE
    await set_user_state(callback.from_user.id, user_state)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=strings.BACK, 
        callback_data=encode_inline_data("chat-edit", "edit-lf-whitelist", "-")
    )
    kb.adjust(1) 
    return await callback.message.edit_text(
        strings.CHAT_EDIT_RESTRICTED_LINKS_WHITELIST_DELETE.format(
            whitelist_links = ", ".join(chat_settings.link_filtering.whitelist)
        ),
        reply_markup=kb.as_markup()
    )

async def show_ban_links_whitelist_add(
        callback: types.CallbackQuery,
        user_state: BotUserState
):
    user_state.state = constants.UserState.EDIT_BOT_LINK_FILTER_ADD
    await set_user_state(callback.from_user.id, user_state)

    kb = InlineKeyboardBuilder()
    kb.button(
        text=strings.BACK, 
        callback_data=encode_inline_data("chat-edit", "edit-lf-whitelist", "-")
    )
    kb.adjust(1) 
    return await callback.message.edit_text(
            strings.CHAT_EDIT_RESTRICTED_LINKS_WHITELIST_ADD,
            reply_markup=kb.as_markup()
        )


async def show_ban_links_whitelist_edit(
        callback: Union[types.CallbackQuery, types.Message], 
        user_state: BotUserState
):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings

    kb = InlineKeyboardBuilder()
    kb.button(
        text=strings.ADD, 
        callback_data=encode_inline_data("chat-edit", "add-lf-whitelist", "-")
    )
    kb.button(
        text=strings.DELETE, 
        callback_data=encode_inline_data("chat-edit", "delete-lf-whitelist", "-")
    )
    kb.button(
        text=strings.BACK, 
        callback_data=encode_inline_data("chat-edit", "edit-banlinks", "-")
    )
    kb.adjust(1) 
    if isinstance(callback, types.CallbackQuery):
        await callback.message.edit_text(
            strings.CHAT_EDIT_RESTRICTED_LINKS_WHITELIST.format(
                whitelist_links = ", ".join(chat_settings.link_filtering.whitelist)
            ), 
            reply_markup=kb.as_markup()
        )
    elif isinstance(callback, types.Message):
        await callback.bot.edit_message_text(
            text = strings.CHAT_EDIT_RESTRICTED_LINKS_WHITELIST.format(
               whitelist_links = ", ".join(chat_settings.link_filtering.whitelist)
            ),
            chat_id=callback.chat.id,
            message_id=user_state.last_message_id,
            inline_message_id=user_state.last_inline_message_id,
            reply_markup=kb.as_markup()
        )
    return 


async def toggle_ban_links_blockall(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    chat_settings.link_filtering.block_all = not chat_settings.link_filtering.block_all
    await services.update_chat_settings_by_id(session, chat_id, chat_settings)
    return await show_ban_links_edit(callback, user_state)
    
async def show_ban_words_edit(
    callback: Union[types.CallbackQuery, types.Message], 
    user_state: BotUserState
):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    punishment_type = {
        'ban': strings.BAN,
        "mute": strings.MUTE
    }.get(chat_settings.restricted_words.punishment.type)
    
    kb = InlineKeyboardBuilder()
    kb.button(
        text=strings.OFF if chat_settings.restricted_words.enabled else strings.ON, 
        callback_data=encode_inline_data("chat-edit", "toggle-bw-enabled", "-")
    ) 
    kb.button(
        text=f"{strings.PUNISHENT}: {punishment_type}", 
        callback_data=encode_inline_data("chat-edit", "toggle-bw-punishment-type")
    )
    kb.button(
        text=f"{strings.PUNISHENT_DURATION}: {chat_settings.restricted_words.punishment.duration}", 
        callback_data=encode_inline_data("chat-edit", "toggle-bw-punishment-time")
    )
    kb.button(
        text=strings.BACK, 
        callback_data=encode_inline_data("chat-edit", "edit", chat_id)
    )
    kb.adjust(1) 
    if isinstance(callback, types.CallbackQuery):
        await callback.message.edit_text(
            strings.CHAT_EDIT_RESTRICTED_WORDS.format(
                is_ban_word_on=strings.YES if chat_settings.restricted_words.enabled else strings.NO,
                punishment_type=punishment_type,
                punishment_duration=chat_settings.restricted_words.punishment.duration,
                punishment_warns_count=chat_settings.restricted_words.punishment.warning_threshold
            ), 
            reply_markup=kb.as_markup()
        )
    elif isinstance(callback, types.Message):
        await callback.bot.edit_message_text(
            text = strings.CHAT_EDIT_RESTRICTED_WORDS.format(
                is_ban_word_on=strings.YES if chat_settings.restricted_words.enabled else strings.NO,
                punishment_type=punishment_type,
                punishment_duration=chat_settings.restricted_words.punishment.duration,
                punishment_warns_count=chat_settings.restricted_words.punishment.warning_threshold
            ),
            chat_id=callback.chat.id,
            message_id=user_state.last_message_id,
            inline_message_id=user_state.last_inline_message_id,
            reply_markup=kb.as_markup()
        )
    return 

async def toggle_ban_words_punishment_time(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState, raw_data: str):
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    punishment_type = {
        'ban': strings.BAN,
        "mute": strings.MUTE
    }.get(chat_settings.restricted_words.punishment.type)
    
    
    if raw_data:
        user_state.state = None
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "edit-banwords", chat_id))
        kb.adjust(1) 
        user_state.state = constants.UserState.EDIT_BOT_RESTRICTED_WORD_DURATION
        user_state.last_message_id = callback.message.message_id
        user_state.last_inline_message_id = callback.inline_message_id
        await callback.message.edit_text(strings.CHAT_EDIT_RW_SELECT_PUNISHMENT_DURATION.format(
            punishment_type=punishment_type,
            punishment_warns_count=chat_settings.restricted_words.punishment.warning_threshold
        ), reply_markup=kb.as_markup())
    return
    
async def toggle_ban_words_punishment_type(callback: types.CallbackQuery, session: AsyncSession, user_state: BotUserState, raw_data: str):
    if not user_state: 
        await callback.answer("Помилка даних, почніть з початку...", show_alert=True)
        return await callback.message.delete()
    
    
    chat_id = user_state.edit.selected_chat_tid
    chat_state = await services.get_chat_from_cache(chat_id)
    chat_settings = chat_state.settings
    
    if raw_data in ["ban", "mute"]:
        chat_settings.restricted_words.punishment.type = raw_data
        await services.update_chat_settings_by_id(session, chat_id, chat_settings)
        await show_ban_words_edit(callback, user_state)
    else:
        kb = InlineKeyboardBuilder()
        kb.button(
            text=f"{strings.BAN} 🔒", 
            callback_data=encode_inline_data("chat-edit", "toggle-bw-punishment-type", "ban")
        )
        kb.row()
        kb.button(
            text=f"{strings.MUTE} 🌐", 
            callback_data=encode_inline_data("chat-edit", "toggle-bw-punishment-type", "mute")
        )
        kb.row()
        kb.button(text=strings.BACK, callback_data=encode_inline_data("chat-edit", "edit-banwords", chat_id))
        kb.adjust(2) 
        await callback.message.edit_text(strings.CHAT_EDIT_RW_SELECT_PUNISHMENT_TYPE.format(
            punishment_warns_count=chat_settings.restricted_words.punishment.warning_threshold
        ), reply_markup=kb.as_markup())
        
    return

@with_session
async def on_welcome_chat(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    prefix, sub_prefix, raw_data = decode_inline_data(callback.data)
    rule_user_id = int(raw_data)

    if rule_user_id != user_id:
        return await callback.answer(strings.WELCOME_NOT_YOUR_RULE, show_alert=True)
    
    user_state = await get_user_state(user_id)
    if not user_state.read_rules_start:
        return await callback.answer(strings.WELCOME_READ_RULES_FIRST, show_alert=True)
    
    now = utcnow()
    time_difference = now - user_state.read_rules_start
    if time_difference < constants.RULE_READ_TIME:
        time_left = (user_state.read_rules_start + constants.RULE_READ_TIME) - now
        return await callback.answer(strings.WELCOME_ALREADY_READ.format(
            time_left=format_timedelta_uk(time_left)
        ), show_alert=True)
    
    user_state.read_rules_start = None 

    await callback.message.answer(strings.WELCOME_RULES_ACCEPTED)
    await callback.bot.restrict_chat_member(
        callback.message.chat.id,
        user_id,
        types.ChatPermissions(
            can_send_messages=True
        )
    )
    return await callback.message.delete() 
