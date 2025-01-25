from app.utils import TIME_DURATION_PATTERN, get_logger
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import ChatMemberUpdatedFilter, IS_NOT_MEMBER, IS_MEMBER, RESTRICTED, ADMINISTRATOR, IS_ADMIN, MEMBER
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from app.config import BOT_TOKEN
from app import commands
from app import handlers
from sqlalchemy.exc import SQLAlchemyError
from aiogram.exceptions import (
    TelegramAPIError, 
    TelegramNetworkError, 
    TelegramUnauthorizedError, 
    TelegramForbiddenError, 
    TelegramBadRequest
)

logger = get_logger()

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

async def global_error_handler(event: types.ErrorEvent):
    exception = event.exception
    update = event.update

    logger.error(f"An error occurred while processing the update: {exception}", exc_info=True)
    if not update.message: return

    if isinstance(exception, TelegramAPIError):
        await update.message.answer(
            "❗ Вибачте, виникла помилка при зверненні до Telegram API. Спробуйте пізніше."
        )
    elif isinstance(exception, TelegramNetworkError):
        await update.message.answer(
            "❗ Виникла проблема з мережею. Перевірте підключення та спробуйте пізніше."
        )
    elif isinstance(exception, TelegramUnauthorizedError):
        await update.message.answer(
            "❗ Ви не авторизовані для виконання цієї дії. Перевірте налаштування бота."
        )
    elif isinstance(exception, TelegramForbiddenError):
        await update.message.answer(
            "❗ У вас немає дозволу виконувати цю дію в даному чаті."
        )
    elif isinstance(exception, TelegramBadRequest):
        await update.message.answer(
            "❗ Невірний запит до Telegram. Перевірте синтаксис команди."
        )
    elif isinstance(exception, SQLAlchemyError):
        await update.message.answer(
            "❗ Вибачте, виникла помилка в базі даних. Спробуйте пізніше."
        )
    else:
        await update.message.answer(
            "❗ Вибачте, сталася непередбачена помилка. Ми працюємо над її виправленням."
        )
    
    return

async def migrate_chat_error_handler(event: types.ErrorEvent):
    update = event.update
    await update.message.reply(
        "❗ Чат був мігрований в супергрупу, спробуйте знову."
    )

dp.callback_query.register(handlers.on_edit_chat_menu, F.data.startswith("chat-edit-menu"))
dp.callback_query.register(handlers.on_edit_chat_settings, F.data.startswith("chat-edit"))
dp.callback_query.register(handlers.on_welcome_chat, F.data.startswith("welcome"))


dp.message.register(handlers.on_rm_duration_message, F.text.regexp(TIME_DURATION_PATTERN))
dp.message.register(handlers.on_init_command, commands.BOT_INIT)
dp.message.register(handlers.on_cat_gif_command, commands.BOT_CAT_GIF)
dp.message.register(handlers.on_bot_mute_command, commands.BOT_MUTE)
dp.message.register(handlers.on_bot_unmute_command, commands.BOT_UNMUTE)
dp.message.register(handlers.on_bot_ban_command, commands.BOT_BAN)
dp.message.register(handlers.on_bot_unban_command, commands.BOT_UNBAN)
dp.message.register(handlers.on_bot_warn_command, commands.BOT_WARN)
dp.message.register(handlers.on_bot_unwarn_command, commands.BOT_UNWARN)



dp.message.register(handlers.on_bot_dice_command, commands.BOT_DICE)
dp.message.register(handlers.on_bot_coin_command, commands.BOT_COIN)



dp.message.register(handlers.on_my_chats_command, commands.BOT_MY_CHATS)
dp.message.register(handlers.on_global_message)



dp.chat_member.register(handlers.on_new_chat_member, ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
dp.chat_member.register(handlers.on_left_chat_member, ChatMemberUpdatedFilter(IS_MEMBER >> IS_NOT_MEMBER))
dp.chat_member.register(
    handlers.on_user_permissions_changed, 
)

dp.error.register(global_error_handler)