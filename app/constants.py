from datetime import timedelta
from enum import Enum
from app import strings

INIT_CMD_COOLDOWN_TIME = timedelta(minutes=30)
MAX_MUTE_MSG_COUNT = 2
MUTE_MSG_TIME_LIMIT = timedelta(minutes=2)
RULE_READ_TIME = timedelta(seconds=20)


class UserState(str, Enum):
    EDIT_BOT_RESTRICTED_WORD_DURATION = "edit_bot_restricted_word_duration"
    EDIT_BOT_LINK_FILTER_ADD = "edit_bot_link_filter_add"
    EDIT_BOT_LINK_FILTER_DELETE = "edit_bot_link_filter_delete"

    NOTHING = "nothing"
    
class UserRole(str, Enum):
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"
    
    BANNED = "banned"


class ChatType(str, Enum):
    PRIVATE = "private"
    CHANNEL = "channel"
    SUPERGROUP = "supergroup"
    GROUP = "group"
    
    @property
    def to_locale(self) -> str:
        return {
            ChatType.PRIVATE: strings.CHAT_TYPE_PRIVATE,
            ChatType.CHANNEL: strings.CHAT_TYPE_CHANNEL,
            ChatType.SUPERGROUP: strings.CHAT_TYPE_SUPERGROUP,
            ChatType.GROUP: strings.CHAT_TYPE_GROUP,
        }.get(self)
    
    @property
    def is_private(self) -> bool:
        return self == ChatType.PRIVATE
    
    @property
    def is_group(self) -> bool:
        return self == ChatType.GROUP
    
    @property
    def is_supergroup(self) -> bool:
        return self == ChatType.SUPERGROUP
    
    @property
    def is_channel(self) -> bool:
        return self == ChatType.CHANNEL



DEFAULT_CHAT_SETTINGS = {
    "moderation": {
        "enabled": False,
        "read_rules": {
            "enabled": False,
            "url": "example-rule.com"
        }
    },
    "notifications": {
        "new_user_notifications": True,
        "left_user_notifications": True,
        "system_thread_id": None,
        "new_user_thread_id": None,
    },
    "restricted_words": {
        "enabled": False,
        "words": ["badword1", "badword2"],
        "punishment": {
            "type": "ban", 
            "duration": "30m", 
            "warning_threshold": 3, 
        }
    },
    "link_filtering": {
        "enabled": False,
        "block_all": False,
        "whitelist": ["example.com", "trustedsite.org"]
    }
}



class Permission(str, Enum):
    VIEW_CHANNEL = "view_channel"
    CREATE_MESSAGE = "create_message"
    DELETE_MESSAGE = "delete_message"
    KICK_MEMBER = "kick_member"
    BAN_MEMBER = "ban_member"
    MANAGE_CHANNEL = "manage_channel"


MEMBER_PERMISSIONS = [
    Permission.VIEW_CHANNEL,
    Permission.CREATE_MESSAGE,
    Permission.DELETE_MESSAGE
]
ADMIN_PERMISSIONS = [
    *MEMBER_PERMISSIONS,
    Permission.KICK_MEMBER,
    Permission.BAN_MEMBER,
]
OWNER_PERMISSIONS = [
    *ADMIN_PERMISSIONS,
    Permission.MANAGE_CHANNEL,
]

ROLE_PERMISSIONS = {
    UserRole.MEMBER: MEMBER_PERMISSIONS,
    UserRole.ADMIN: ADMIN_PERMISSIONS,
    UserRole.OWNER: OWNER_PERMISSIONS
}