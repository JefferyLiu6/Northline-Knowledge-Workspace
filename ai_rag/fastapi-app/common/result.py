from datetime import date, datetime
from typing import Any, List

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from tortoise import Model

# The output format of the time field. If not specified, datetime will be sequenced
# 2026-09-03T21:09:50+08:00 This ISO string, which is shown directly in tables that are hard to read,
# This is a unified year-month-day time: minutes: seconds, and the front end will be shown directly.
DATETIME_ENCODERS = {
    datetime: lambda value: value.strftime("%Y-%m-%d %H:%M:%S"),
    date: lambda value: value.strftime("%Y-%m-%d"),
}



class Result(BaseModel):
    # Operations status code, string type: "200" successful, "500" failed, "401 not login", "403" not authorized
    code: str
    # Hints, if you fail, the front end pops it out and shows it to users.
    msg: str
    # Business data, list, object or string when successful, empty when failed
    data: Any = None

    @staticmethod
    def success(data: Any = None):
        json_data = None
        if data is not None:
            # PageInfo is a pydantic model, jsonable_encoder will allow pydontic to sequence itself first.
            # The datetime inside was turned into an ISO string at that point, and the downtime custom_encoder could never be inserted.
            # Distribute as normal before the datetime in the list goes to a uniform time formatting
            if isinstance(data, PageInfo):
                data = {"total": data.total, "list": data.list}
            # All interfaces are returned from here and the time format is harmonized here.
            json_data = jsonable_encoder(data, custom_encoder=DATETIME_ENCODERS)
        return Result(code="200", msg="Request successful", data=json_data)

    @staticmethod
    def error(msg: str = "Request failed"):
        return Result(code="500", msg=msg)


class PageInfo(BaseModel):
    # Total strips, front end of which rewrite the tab
    total: int = 0
    # Current page data, with which the front end rewrites tables
    list: List[Any] = []
