"""Login, registration, password change, and get current logged-in account."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from common.auth import get_current_user
from common.result import Result
from models import User
from service import account_service

# This road doesn't prefix, so the path is /login, /register,
# The address written in the front end
router = APIRouter()


class Account(BaseModel):
    # Only parts of the field may be filled in at front data.form, so all four fields are allowed to be None,
    # Which one must be judged by the service level and given a hint
    username: str | None = None
    password: str | None = None
    newPassword: str | None = None
    confirmPassword: str | None = None


@router.post("/login")
async def login(account: Account, response: Response):
    # FastAPI automatically interprets the request body JSON into an object by using a field name for Account, and then uses the user 's name.
    # The route level doesn't make business judgements. Give the account code to service.
    data = await account_service.login(account.username, account.password)
    # Data contains token and user information, Result. access packaged back to front
    response.delete_cookie("file_session", path="/files")
    response.set_cookie("file_session", data["token"], httponly=True, samesite="strict", path="/", max_age=86400)
    return Result.success(data)


@router.post("/register")
async def register(account: Account):
    # Register to three fields in Account, new Password
    await account_service.register(account.username, account.password, account.confirmPassword)
    return Result.success()


@router.put("/updatePassword")
async def update_password(account: Account, current_user: User = Depends(get_current_user)):
    # Changed must be your own password. User ID is parsed from token and no front-end id
    await account_service.update_password(current_user, account.password, account.newPassword)
    # Registration successfully does not return any data, front end only looks at code 200
    return Result.success()


@router.get("/currentUser")
async def current_user(user: User = Depends(get_current_user)):
    return Result.success(account_service.account_dict(user))


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("file_session", path="/files")
    response.delete_cookie("file_session", path="/")
    return Result.success()
