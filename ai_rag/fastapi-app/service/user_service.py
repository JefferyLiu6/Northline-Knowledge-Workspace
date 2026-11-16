from service.file_service import public_url
"""User-managed business logic."""

from typing import List
from common.passwords import hash_password

from common.exception_handler import CustomException
from common.result import PageInfo
from models import User
from service.account_service import ROLES, STATUSES


def user_dict(user: User) -> dict:
    # Each column of the table is taken from this field. Passwords are not entered. The passwords are not visible on the list page.
    return {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "avatar": public_url(user.avatar),
        "role": user.role,
        "phone": user.phone,
        "email": user.email,
        "status": user.status,
        "create_time": user.create_time,
        "update_time": user.update_time,
    }


async def add(payload: dict) -> None:
    username = payload.get("username")
    # The account number is a login and must be valued.
    if not username:
        raise CustomException("Enter your username")
    # The only account that's missing is the duplicate. No insertion logic.
    if await User.get_or_none(username=username):
        raise CustomException("Account duplication")
    # The window is given by default to USER, and here we go back to the bottom to prevent a direct pass-through of the page.
    role = payload.get("role") or "USER"
    if role not in ROLES:
        raise CustomException("Role Parameter Error")
    await User.create(
        username=username,
        # Leave the password box empty to the default password, which corresponds to the location hint in the window
        password=hash_password(payload.get("password") or "123456"),
        # Use the top of the account if you do not fill out a name. Make sure that the list page is not empty.
        name=payload.get("name") or username,
        avatar=payload.get("avatar"),
        role=role,
        phone=payload.get("phone"),
        email=payload.get("email"),
        # The new account can be entered directly without the default normal state
        status=payload.get("status") or "NORMAL",
    )


async def update(current_user: User, user_id: int | None, update_data: dict) -> None:
    if user_id is None:
        raise CustomException("User ID cannot be empty")
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise CustomException("User not found")
    # The administrator can change anyone. Normal users can only change themselves.
    if current_user.role != "ADMIN" and current_user.id != user.id:
        raise CustomException("No operation permissions", "403")
    # Normal users are not allowed to change their roles and account status
    if current_user.role != "ADMIN":
        update_data.pop("role", None)
        update_data.pop("status", None)
    # The role must be legal, but without it skips the check.
    if update_data.get("role") is not None and update_data["role"] not in ROLES:
        raise CustomException("Role Parameter Error")
    # If you pass a state, it must be legal. If you don't, you skip the check.
    if update_data.get("status") is not None and update_data["status"] not in STATUSES:
        raise CustomException("Error parameter for account status")
    await User.filter(id=user.id).update(**update_data)


async def delete(current_user: User, user_id: int) -> None:
    # Deleting yourself would cause the current session to expire immediately, and the page was parked on an invalid login.
    if current_user.id == user_id:
        raise CustomException("Could not close temporary folder: %s")
    await User.filter(id=user_id).delete()


async def delete_batch(current_user: User, ids: List[int]) -> None:
    # The ticking includes a whole batch of yourself, not "jump over and delete someone else."
    # To avoid a user thinking it's all deleted and actually missing one.
    if current_user.id in ids:
        raise CustomException("Could not close temporary folder: %s")
    await User.filter(id__in=ids).delete()


async def select_by_id(current_user: User, user_id: int) -> dict:
    # Normal users can only check their own files to prevent a change of address bar.
    if current_user.role != "ADMIN" and current_user.id != user_id:
        raise CustomException("No operation permissions", "403")
    user = await User.get_or_none(id=user_id)
    if user is None:
        raise CustomException("User not found")
    return user_dict(user)


async def select_all(name: str = "") -> List[dict]:
    users = await User.filter(name__contains=name).order_by("-id")
    return [user_dict(user) for user in users]


async def select_page(name: str = "", role: str = "", page_num: int = 1, page_size: int = 10) -> PageInfo:
    # Name from the top name input box, containins is a blurry match;
    # When a string is empty, like '%' matches all records.
    query = User.filter(name__contains=name)
    # role from the role frame, only the character is selected to add precise matching conditions
    if role:
        query = query.filter(role=role)
    # id in reverse order, with new users at the top;
    # listt skips the previous pages, limit takes the number of bars on the current page
    users = await query.order_by("-id").offset((page_num - 1) * page_size).limit(page_size)
    # The total number is to be counted with the same query without a page break, which makes up the total number of pages.
    total = await query.count()
    return PageInfo(total=total, list=[user_dict(user) for user in users])
