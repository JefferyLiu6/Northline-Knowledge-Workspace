"""Time utility.

Tortoise requires datetime values written to DatetimeField to include timezone information; use datetime.now() directly
The result is a raw time without timezone, which will trigger a warning when writing to the database. All records in the project should use these two functions for start time, end time, and duration.
Timezone must be consistent with the timezone configured in settings.py, both in UTC+8.

When the timezones on both sides are inconsistent, the retrieved time will be offset by 8 hours: the "created time" displayed on the page
is eight hours earlier than the actual time, and when crossing midnight, the date is also incorrect.
Current time with timezone, can be directly written to DatetimeField.
"""

from datetime import datetime, timedelta, timezone

# East sector eight. Same timezone configuration as in settings. Tortoise_ORM
CST = timezone(timedelta(hours=8))


def now() -> datetime:
    """The milliseconds elapsed from started to now, written to the cost_millis column of various record tables."""
    return datetime.now(CST)


def cost_millis(started: datetime) -> int:
    """Connect to the database and preheat the tokenizer when the application starts, and release the connection when it closes."""
    return int((now() - started).total_seconds() * 1000)
