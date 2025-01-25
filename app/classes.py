import re
from datetime import datetime, timedelta, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DurationString(str):
    pattern = r"^(?:(\d+)M)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$"

    def __new__(cls, value) -> "DurationString":
        if not re.fullmatch(cls.pattern, value):
            print("BAD")
            raise ValueError("Invalid duration format")
        return str.__new__(cls, value)

    def to_timedelta(self) -> timedelta:
        match = re.fullmatch(self.pattern, self)
        if not match:
            raise ValueError("Invalid duration format")
        months, days, hours, minutes, seconds = [int(val) if val else 0 for val in match.groups()]
        total_seconds = seconds + minutes * 60 + hours * 3600 + days * 86400 + months * 2592000
        return timedelta(seconds=total_seconds)
    
    def to_datetime(self, utc: bool = True) -> datetime:
        if utc:
            return utcnow() + self.to_timedelta()
        return datetime.now() + self.to_timedelta()

    @staticmethod
    def from_timedelta(td: timedelta) -> str:
        total_seconds = int(td.total_seconds())
        months, remainder = divmod(total_seconds, 2592000)
        days, remainder = divmod(remainder, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        result = []
        if months:
            result.append(f"{months}M")
        if days:
            result.append(f"{days}d")
        if hours:
            result.append(f"{hours}h")
        if minutes:
            result.append(f"{minutes}m")
        if seconds:
            result.append(f"{seconds}s")
        return "".join(result)
    
    def limit_timedelta(self, max_duration: timedelta) -> "DurationString":
        current_duration = self.to_timedelta()
        if current_duration > max_duration:
            new_duration = max_duration
        else:
            new_duration = current_duration
        
        new_duration_str = self.from_timedelta(new_duration)
        return DurationString(new_duration_str)