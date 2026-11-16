from service.file_service import public_url
"""Login and registration business logic related to the current account."""

from common.auth import create_token
from common.passwords import hash_password, verify_password
from common.exception_handler import CustomException
from models import User

# The system has only two roles: the manager ADMIN, the user USER
ROLES = {"ADMIN", "USER"}
STATUSES = {"NORMAL", "DISABLED"}


def account_dict(user: User, token: str | None = None) -> dict:
    """Account information is output with desensitization, without returning the password field."""
    # This dictionary is the content of the front-end res. data, and also the xm-user that was stored in localStorage,
    # The top right corner of the page has a name and header, a road guard to judge the character. It's all here.
    data = {
        "id": user.id,
        "username": user.username,
        "name": user.name,
        "avatar": public_url(user.avatar),
        "role": user.role,
        "phone": user.phone,
        "email": user.email,
        "status": user.status,
    }
    # Only login interfaces pass token. Other interfaces repeat this function without token
    if token:
        data["token"] = token
    return data


async def login(username: str | None, password: str | None) -> dict:
    # Check users by account, username has a single index and hits one at most.
    user = await User.get_or_none(username=username)
    # The account does not exist and the password error is merged into a single hint, without telling each other which step was wrong.
    if user is None or not verify_password(password, user.password):
        raise CustomException("Invalid account or password")
    # The password is correct and the status is still to be seen. The administrator's deactivated account number in the user administration is not allowed to log in.
    if user.status != "NORMAL":
        raise CustomException("Account has been disabled")
    # Verify all through, issue token and return with user information
    return account_dict(user, create_token(user))


async def register(username: str | None, password: str | None, confirm_password: str | None) -> None:
    # Front rule has stopped empty value once and backend again to prevent direct interfaces from bypassing the page
    if not username or not password:
        raise CustomException("Account and password cannot be empty")
    # The two password consistency backends are also reviewed, and the same is to prevent direct switching over pages.
    if password != confirm_password:
        raise CustomException("Passwords entered twice are inconsistent")
    # Repeat check of account number and the hits are interrupted. No insertion logic
    if await User.get_or_none(username=username):
        raise CustomException("Account duplication")
    # Registration portals can only create ordinary users and administrator accounts are added by the manager to user management
    await User.create(
        username=username,
        password=hash_password(password),
        # By default, the name is entered into an account and the user can change its personal profile page to a real name in chapter 03
        name=username,
        role="USER",
        status="NORMAL",
    )


async def update_password(
    current_user: User,
    password: str | None,
    new_password: str | None,
) -> None:
    # The original password must be secured to prevent people from changing the code while the page is unlocked.
    if not verify_password(password, current_user.password):
        raise CustomException("Original password is incorrect")
    if not new_password:
        raise CustomException("Please enter a new password")
    # The old code is the same as the new one. Just stop it.
    if verify_password(new_password, current_user.password):
        raise CustomException("New password cannot be the same as the original password")
    # Update with current login user id, no change to head
    await User.filter(id=current_user.id).update(password=hash_password(new_password))
