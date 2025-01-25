import asyncio
from app.bad_word import _get_cached_model
from app.database import close_engine
from app.utils import get_logger
from app.bot import bot, dp, Bot, types
from app.utils import stop_telethon_client
logger = get_logger()

async def set_private_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Почати"),
        types.BotCommand(command="help", description="Допомога"),
        types.BotCommand(command="cat_gif", description="Гіфка котика"),
        types.BotCommand(command="my_chats", description="Налаштування чатів"),
    ]
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllPrivateChats())

async def set_admin_commands(bot: Bot):
    commands = [
        types.BotCommand(command="mute", description="Видати мут ({час} {причина})"),
        types.BotCommand(command="unmute", description="Зняти мут"),
        types.BotCommand(command="warn", description="Видати попередження ({причина})"),
        types.BotCommand(command="unwarn", description="Зняти попередження"),
        types.BotCommand(command="ban", description="Видати бан ({час} {причина})"),
        types.BotCommand(command="unban", description="Зняти бан"),
        types.BotCommand(command="start", description="Почати"),
        types.BotCommand(command="help", description="Допомога"),
    ]
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllChatAdministrators())

async def set_chats_commands(bot: Bot):
    commands = [
        types.BotCommand(command="start", description="Почати"),
        types.BotCommand(command="help", description="Допомога"),
        types.BotCommand(command="cat_gif", description="Гіфка котика"),
    ]
    await bot.set_my_commands(commands, scope=types.BotCommandScopeAllGroupChats())


async def setup_bot_commands(bot: Bot):
    await set_private_commands(bot)
    await set_admin_commands(bot)
    await set_chats_commands(bot)


async def main() -> None:
    try:
        logger.info('Starting bot...')
        _get_cached_model()
        await setup_bot_commands(bot)
        await dp.start_polling(bot)
        
    except asyncio.CancelledError:
        logger.warning('Bot was cancelled.')
    except KeyboardInterrupt:
        logger.info('Bot interrupted by user.')
    finally:
        logger.info('Stopping bot...')
        logger.info('Bot stopped successfully.')
        await close_engine()
        await stop_telethon_client()
        logger.info('Database connection closed.')

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('Application stopped by user.')
