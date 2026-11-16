"""User Management Interface."""

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from common.auth import get_current_user, require_admin
from common.result import Result
from models import User
from service import user_service

# This root with prefix = "/user", so all the paths below are automatically added /user
router = APIRouter(prefix="/user")


class UserPayload(BaseModel):
    # From_attribates allows the model to be constructed directly from an ORM object
    model_config = ConfigDict(from_attributes=True)

    # All fields are allowed to be None, and the front end window may have only a few of them filled out.
    # Which must be judged by service and given a hint
    id: int | None = None
    username: str | None = None
    password: str | None = None
    name: str | None = None
    avatar: str | None = None
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    status: str | None = None


@router.post("/add")
async def add(payload: UserPayload, _: User = Depends(require_admin)):
    # The only thing that is left to be mentioned in this post is the fact that it's not possible for a person to have access to the Internet.
    # Unfilled fields are not dictionaries. Leave them to service for default
    await user_service.add(payload.model_dump(exclude_unset=True))
    return Result.success()


@router.put("/update")
async def update(payload: UserPayload, current_user: User = Depends(get_current_user)):
    # Account number and password are not allowed to change via this interface /updatepassword
    update_data = payload.model_dump(exclude_unset=True, exclude={"id", "username", "password"})
    await user_service.update(current_user, payload.id, update_data)
    return Result.success()


@router.delete("/delete/{user_id}")
async def delete(user_id: int, current_user: User = Depends(require_admin)):
    # The user_id is written on the path, as it is a locator for deleted objects and not an operational data set;
    # We're gonna need it here, so we don't write down the line.
    await user_service.delete(current_user, user_id)
    return Result.success()


@router.delete("/deleteBatch")
async def delete_batch(ids: List[int], current_user: User = Depends(require_admin)):
    # FastAPI parses the request body as a list of integers.
    await user_service.delete_batch(current_user, ids)
    return Result.success()


@router.get("/selectById/{user_id}")
async def select_one(user_id: int, current_user: User = Depends(get_current_user)):
    return Result.success(await user_service.select_by_id(current_user, user_id))


@router.get("/selectAll")
async def select_all(name: str = "", _: User = Depends(require_admin)):
    return Result.success(await user_service.select_all(name))


@router.get("/selectPage")
async def select_page(
    # The name and file query parameters from the address bar, which do not pass through empty strings at any time, indicate that this filter is not available
    name: str = "",
    role: str = "",
    # Page numbers and number of lines per page are also derived from query parameters, given default values and can run without sending the front
    page_num: int = 1,
    page_size: int = 10,
    # Deepends (require_admin) will first parse token in the request.
    # You throw 403 without the administrator. The function doesn't execute it at all.
    _: User = Depends(require_admin),
):
    return Result.success(await user_service.select_page(name, role, page_num, page_size))
