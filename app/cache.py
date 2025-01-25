from typing import Optional
from datetime import datetime
from aiocache import SimpleMemoryCache
from app.models import TelegramChat
from uuid import UUID
from app.schemas import BotUserState
from app.constants import MAX_MUTE_MSG_COUNT, MUTE_MSG_TIME_LIMIT

user_cache = SimpleMemoryCache()
user_message_cache = SimpleMemoryCache(timeout=120)
chat_cache = SimpleMemoryCache(timeout=120)

async def set_user_state(user_id: int, state: BotUserState):
    await user_cache.set(f"user_state_{user_id}", state)

async def get_user_state(user_id: int) -> BotUserState:
    state = await user_cache.get(f"user_state_{user_id}")
    return state if state else BotUserState(user_id=user_id)

async def clear_user_state(user_id: int):
    await user_cache.delete(f"user_state_{user_id}")


async def set_chat_state(chat_id: UUID | int, state: TelegramChat):
    cache_key = f"chat_{chat_id}"
    return await chat_cache.set(cache_key, state)

async def get_chat_state(chat_id: UUID | int) -> Optional[TelegramChat]:
    cache_key = f"chat_{chat_id}"
    state = await chat_cache.get(cache_key)
    return state if state else None

async def clear_chat_state(chat_id: UUID):
    await chat_cache.delete(f"chat_{chat_id}")

################################################################################

async def increment_user_message_count(chat_id: UUID | int, user_id: int) -> Optional[int]:
    cache_key = f"chat_{chat_id}_user_{user_id}"
    
    current_data = await user_message_cache.get(cache_key)
    current_count = current_data["count"] if current_data else 0
    last_msg_time = current_data["last_message_time"] if current_data else datetime.now()

    if datetime.now() - last_msg_time > MUTE_MSG_TIME_LIMIT:
        current_count = 0 

    current_count += 1
    new_data = {
        "count": current_count,
        "last_message_time": datetime.now()
    }
    await user_message_cache.set(cache_key, new_data)
    return current_count

async def check_user_spam_status(chat_id: UUID | int, user_id: int) -> bool:
    cache_key = f"chat_{chat_id}_user_{user_id}"
    data = await user_message_cache.get(cache_key)

    if not data or data["count"] < MAX_MUTE_MSG_COUNT:
        return False

    return True

async def clear_user_message_state(chat_id: UUID | int, user_id: int):
    cache_key = f"chat_{chat_id}_user_{user_id}"
    await user_message_cache.delete(cache_key)