from aiogram.filters import CommandStart, Command
from app.classes import DurationString
from app.utils import create_parser, ArgSpec

BOT_DICE = Command("dice")
BOT_COIN = Command("coin")
BOT_CAT_GIF = Command("cat_gif")


BOT_INIT = Command("init")
BOT_MY_CHATS = Command("my_chats")

BOT_MUTE = Command("mute")
BOT_UNMUTE = Command("unmute")

BOT_BAN = Command("ban")
BOT_UNBAN = Command("unban")


BOT_WARN = Command("warn")
BOT_UNWARN = Command("unwarn")


BAN_COMMAND_PARSER = create_parser({
    'duration': ArgSpec(type=int),
    'reason': ArgSpec(type=DurationString),
    'username': ArgSpec(type=str, optional=True, default=None)
})
UNBAN_COMMAND_PARSER = create_parser({
    'username': ArgSpec(type=str, optional=True, default=None)
})

WARN_COMMAND_PARSER = create_parser({
    'reason': ArgSpec(type=str),
    'username': ArgSpec(type=str, optional=True, default=None)
})
