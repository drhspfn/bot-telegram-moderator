from datetime import datetime, timezone, timedelta
from functools import lru_cache
import logging
from pathlib import Path
import random
import re
import aiohttp
from typing import Any, List, Optional, Tuple, Type, Union, cast, Dict
from app import constants
from app import strings
from app.classes import DurationString
from app.config import DEBUG_MODE, API_HASH, API_ID, TENOR_API_KEY
from telethon import TelegramClient
from telethon.tl.types import (
    ChannelParticipantAdmin, 
    ChannelParticipantCreator, 
    ChannelParticipantBanned, 
    ChannelParticipantLeft,
    ChannelParticipant,
    ChatFull,
    ChatBannedRights,
    ChatAdminRights,
    User
)
from telethon.tl.functions.channels import GetParticipantRequest, GetFullChannelRequest
import dataclasses
from app.schemas import TelegramUserPermissions


telethon_client = TelegramClient('bot_client', API_ID, API_HASH)



TIME_DURATION_PATTERN = r"^(\d+[smhdM])+$"


class CustomFormatter(logging.Formatter):
    def __init__(self, max_func_name_length=15, *args, **kwargs) -> logging.Formatter:
        if not isinstance(max_func_name_length, int):
            raise ValueError("max_func_name_length must be an integer.")
        self.max_func_name_length = max_func_name_length
        super().__init__(*args, **kwargs)

    def format(self, record) -> str:
        if len(record.funcName) > self.max_func_name_length:
            record.funcName = record.funcName[:
                                              self.max_func_name_length-3] + "..."
        return super().format(record)

class InfoOrLowerFilter(logging.Filter):
    def __init__(self, levelno: int) -> logging.Filter:
        super().__init__()
        self.levelno = levelno

    def filter(self, record) -> bool:
        return record.levelno <= self.levelno



async def get_user_permissions(client: TelegramClient, chat_id: int, user_id: int, default_permissions: TelegramUserPermissions) -> TelegramUserPermissions:
    try:
        participant_full = await client(GetParticipantRequest(channel=chat_id, participant=user_id))
        participant = participant_full.participant

        permissions = default_permissions.copy()

        if isinstance(participant, ChannelParticipantCreator):
            permissions.is_member = True
            permissions.can_send_messages = True
            permissions.can_send_audios = True
            permissions.can_send_documents = True
            permissions.can_send_photos = True
            permissions.can_send_videos = True
            permissions.can_send_video_notes = True
            permissions.can_send_voice_notes = True
            permissions.can_send_polls = True
            permissions.can_send_other_messages = True
            permissions.can_add_web_page_previews = True
            permissions.can_change_info = True
            permissions.can_invite_users = True
            permissions.can_pin_messages = True
            permissions.can_manage_topics = True

        elif isinstance(participant, ChannelParticipantAdmin):
            permissions.is_member = True
            admin_rights = participant.admin_rights
            permissions.can_invite_users = admin_rights.invite_users
            permissions.can_pin_messages = admin_rights.pin_messages
            permissions.can_change_info = admin_rights.change_info

        elif isinstance(participant, (ChannelParticipantBanned, ChannelParticipantLeft)):
            permissions.is_member = False

        elif isinstance(participant, ChannelParticipant):
            permissions.is_member = True

        return permissions

    except Exception as e:
        print(f"Error getting user permissions: {e}")
        return TelegramUserPermissions()

async def get_chat_members(chat_id: int) -> List[Tuple[str, int, TelegramUserPermissions]]:
    if not telethon_client.is_connected():
        await telethon_client.start()

    chat_members = []
    
    full_channel:ChatFull = await telethon_client(GetFullChannelRequest(chat_id))
    default_banned_rights:ChatBannedRights = full_channel.chats[0].default_banned_rights
    # default_admin_rights:ChatAdminRights = full_channel.chats[0].admin_rights

    default_permissions = TelegramUserPermissions(
        is_member=True,
        can_send_messages=not default_banned_rights.send_messages,
        can_send_audios=not default_banned_rights.send_audios,
        can_send_documents=not default_banned_rights.send_docs,
        can_send_photos=not default_banned_rights.send_photos,
        can_send_videos=not default_banned_rights.send_videos,
        can_send_video_notes=not default_banned_rights.send_roundvideos,
        can_send_voice_notes=not default_banned_rights.send_voices,
        can_send_polls=not default_banned_rights.send_polls,
        can_change_info=not default_banned_rights.change_info,
        can_invite_users=not default_banned_rights.invite_users,
        can_pin_messages=not default_banned_rights.pin_messages,
        can_manage_topics=not default_banned_rights.manage_topics
    )

    async for member in telethon_client.iter_participants(chat_id):
        # member = cast(User, member)
        if member.is_self or member.bot:
            continue
        
        permissions = await get_user_permissions(telethon_client, chat_id, member.id, default_permissions)
        chat_members.append((member.username, member.id, permissions))

    return chat_members

async def stop_telethon_client():
    if telethon_client.is_connected():
        await telethon_client.disconnect()

@lru_cache()
def get_logger() -> logging.Logger:
    logger = logging.getLogger("aiogram")

    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)

    formatter = CustomFormatter(
        max_func_name_length=15,
        fmt='%(levelname)-8s | %(name)-20s | %(funcName)-15s | %(asctime)-8s : %(message)s',
        datefmt='%H:%M:%S'
    )

    debug_no_level_formatter = logging.Formatter(
        '%(asctime)s | %(name)-20s | %(funcName)s : %(message)s',
        datefmt='%H:%M:%S'
    )

    log_dir = Path(f"logs/{datetime.now().strftime('%Y-%m-%d')}")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler_info = logging.FileHandler(
        f'{log_dir}/info.log', encoding='utf-8')
    file_handler_info.setLevel(logging.INFO)
    file_handler_info.setFormatter(formatter)
    file_handler_info.addFilter(InfoOrLowerFilter(logging.INFO))

    file_handler_error = logging.FileHandler(
        f'{log_dir}/error.log', encoding='utf-8')
    file_handler_error.setLevel(logging.ERROR)
    file_handler_error.setFormatter(formatter)

    if DEBUG_MODE:
        file_handler_debug = logging.FileHandler(
            f'{log_dir}/debug.log', encoding='utf-8')
        file_handler_debug.setLevel(logging.DEBUG)
        file_handler_debug.setFormatter(debug_no_level_formatter)
        file_handler_debug.addFilter(InfoOrLowerFilter(logging.DEBUG))

    logger.addHandler(file_handler_info)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler_error)
    if DEBUG_MODE: logger.addHandler(file_handler_debug)

    return logger


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def to_timestamp(date: datetime | None) -> int | None:
    if isinstance(date, timedelta):
        date = datetime.now(timezone.utc) + date  
        
    if date:
        date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date  
        return int(date.timestamp()) 
    return None

def subtract_datetimes(dt1: datetime, dt2: datetime) -> timedelta:
    if dt1.tzinfo is None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    else:
        dt1 = dt1.astimezone(timezone.utc)

    if dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    else:
        dt2 = dt2.astimezone(timezone.utc)

    return dt1 - dt2

def format_timedelta_uk(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    days_forms = {
        'one': 'день',
        'few': 'дні',
        'many': 'днів'
    }
    
    hours_forms = {
        'one': 'годину',
        'few': 'години',
        'many': 'годин'
    }
    
    minutes_forms = {
        'one': 'хвилину',
        'few': 'хвилини',
        'many': 'хвилин'
    }
    
    seconds_forms = {
        'one': 'секунду',
        'few': 'секунди',
        'many': 'секунд'
    }
    
    def get_plural_form(number: int, forms: dict) -> str:
        if number % 10 == 1 and number % 100 != 11:
            return forms['one']
        elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
            return forms['few']
        else:
            return forms['many']
    
    parts = []
    
    if days > 0:
        parts.append(f"{days} {get_plural_form(days, days_forms)}")
    if hours > 0:
        parts.append(f"{hours} {get_plural_form(hours, hours_forms)}")
    if minutes > 0:
        parts.append(f"{minutes} {get_plural_form(minutes, minutes_forms)}")
    if seconds > 0 or not parts:
        parts.append(f"{seconds} {get_plural_form(seconds, seconds_forms)}")
    
    return " ".join(parts)

def format_timedelta_ua(delta: timedelta) -> str:
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    day_str = get_day_declination(days)
    hour_str = get_hour_declination(hours)
    minute_str = get_minute_declination(minutes)
    second_str = get_second_declination(seconds)

    time_parts = []
    if days > 0:
        time_parts.append(f"{days} {day_str}")
    if hours > 0:
        time_parts.append(f"{hours} {hour_str}")
    if minutes > 0:
        time_parts.append(f"{minutes} {minute_str}")
    if seconds > 0:
        time_parts.append(f"{seconds} {second_str}")
    
    return " ".join(time_parts)

def get_day_declination(days: int) -> str:
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    elif 2 <= days % 10 <= 4 and not (11 <= days % 100 <= 14):
        return "дні"
    else:
        return "днів"

def get_hour_declination(hours: int) -> str:
    if hours % 10 == 1 and hours % 100 != 11:
        return "година"
    elif 2 <= hours % 10 <= 4 and not (11 <= hours % 100 <= 14):
        return "години"
    else:
        return "годин"

def get_minute_declination(minutes: int) -> str:
    if minutes % 10 == 1 and minutes % 100 != 11:
        return "хвилина"
    elif 2 <= minutes % 10 <= 4 and not (11 <= minutes % 100 <= 14):
        return "хвилини"
    else:
        return "хвилин"

def get_second_declination(seconds: int) -> str:
    if seconds % 10 == 1 and seconds % 100 != 11:
        return "секунда"
    elif 2 <= seconds % 10 <= 4 and not (11 <= seconds % 100 <= 14):
        return "секунди"
    else:
        return "секунд"
    

def encode_inline_data(prefix: str, sub_prefix: Optional[str], data: Optional[Union[int, str]]=None) -> str:
    sub_prefix = sub_prefix or ""
    data = data if data is not None else ""

    if not isinstance(data, str):
        data = str(data)
    data = data.replace("_", "__") 
    data = data.replace("-", "*") 
    
    ret = f"{prefix}_{sub_prefix}_{data}"
    print('ret: ', ret)
    return ret

def decode_inline_data(data: str) -> Optional[Tuple[str, Optional[str], Optional[Union[int, str]]]]:
    match = re.match(r"([a-zA-Z0-9_-]+)_([a-zA-Z0-9_-]+)?_(.*)", data)
    if match:
        prefix, sub_prefix, raw_data = match.groups()
        sub_prefix = None if sub_prefix is None else sub_prefix
        if raw_data:
            try:
                return prefix, sub_prefix, int(raw_data)
            except ValueError:
                raw_data = raw_data.replace("__", "_")
                raw_data = raw_data.replace("*", "-")
                return prefix, sub_prefix, raw_data
        else:
            return prefix, sub_prefix, None
    return None, None, None

def check_admin_rights(
    role: constants.UserRole,
    required_rights: List[constants.Permission] = None,
    required_role: List[constants.UserRole] = None
) -> bool:
    
    if not isinstance(role, constants.UserRole): role = constants.UserRole(role)
    if not isinstance(required_role, list): required_role = [required_role]
    
    if required_role and role not in required_role:
        return False

    if required_rights:
        user_permissions = constants.ROLE_PERMISSIONS.get(role, [])
        required_rights_set = set(required_rights)
        user_permissions_set = set(user_permissions)
        return required_rights_set.issubset(user_permissions_set)

    return True

def parse_mute_command(text: str) -> Tuple[Optional[DurationString], Optional[str]]:
    parts = text.split(maxsplit=2)
    if len(parts) < 2:
        return None, None

    try:
        duration = DurationString(parts[1])
    except ValueError:
        return None, None
    
    reason = parts[2] if len(parts) > 2 else None
    return duration, reason

def parse_command_args(
    text: str,
    arg_types: List[Type]
) -> Tuple[Optional[List[Any]], Optional[str]]:
    parts = text.split()
    if len(parts) - 1 < len(arg_types):
        return None, strings.COMMAND_ARGS_INSUFFICIENT
    
    args = []
    for i, arg_type in enumerate(arg_types):
        try:
            value = arg_type(parts[i + 1])
            args.append(value)
        except ValueError as e:
            return None, strings.COMMAND_ARG_INVALID_TYPE.format(
                arg_number = i + 1,
                expected_type = strings.type_locale(arg_type),
                received_value = parts[i + 1]
            ) 
    
    return args, None

@dataclasses.dataclass
class ArgSpec:
    type: Type
    optional: bool = False
    default: Any = None


def create_parser(arg_spec: Dict[str, ArgSpec]):
    def parse_command_args(text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        parts = text.split()[1:]
        parsed_args = {}
        
        used_parts = 0
        
        for arg_name, spec in arg_spec.items():
            if used_parts < len(parts):
                try:
                    parsed_value = spec.type(parts[used_parts])
                    parsed_args[arg_name] = parsed_value
                    used_parts += 1
                except (ValueError, IndexError):
                    if spec.optional:
                        if spec.default is not None:
                            parsed_args[arg_name] = spec.default
                    else:
                        return None, strings.COMMAND_ARG_INVALID_TYPE.format(
                        arg_number=used_parts + 1,
                        expected_type=spec.type.__name__,
                        received_value=parts[used_parts],
                    )
            else:
                if not spec.optional:
                    return None,  strings.COMMAND_ARGS_INSUFFICIENT.format(
                        expected_args=", ".join(arg_spec.keys())
                    )
                if spec.default is not None:
                    parsed_args[arg_name] = spec.default
        
        return parsed_args, None
    
    return parse_command_args


def extract_urls(text: str) -> list:
    url_pattern = r'((https?:\/\/)?([\w\-]+\.[\w\.-]+)(\/[^\s]*)?)'
    matches = re.findall(url_pattern, text)
    return [match[0] for match in matches]

def is_link(text):
    url_pattern = re.compile(
        r'^(https?:\/\/)?'
        r'([\da-z\.-]+)\.'
        r'([a-z\.]{2,6})' 
        r'([\/\w\.-]*)*\/?$'
    )
    return bool(url_pattern.match(text))

def compare_links(link:str, whitelist: List[str]) -> bool:
    def normalize_url(url: str) -> str:
        return url.replace("http://", "").replace("https://", "").strip("/")
    
    normalized_link = normalize_url(link)
    normalized_whitelist = [normalize_url(item) for item in whitelist]
    
    return normalized_link in normalized_whitelist




async def get_random_cat_gif() -> Optional[str]:
    url = "https://g.tenor.com/v1/search"
    params = {
        "q": "cat",
        "key": TENOR_API_KEY,
        "limit": 50,
        "random": "true",
        "media_filter": "gif"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            data = await response.json()
            if response.status == 200:
                gifs = data.get('results', [])
                urls = [gif['media'][0]['gif']['url'] for gif in gifs]
                return random.choice(urls)
    return None
