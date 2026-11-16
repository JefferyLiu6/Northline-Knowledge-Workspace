from datetime import datetime, timedelta, timezone

import hashlib
import hmac
import jwt
from fastapi import Header

from common.exception_handler import CustomException
from models import User
from settings import JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET


def create_token(user: User) -> str:
    # Expiration time = hours of configuration for current UTC time + settings. py with 24 hours
    expire_time = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    # sub stored user id, with which each protected interface will be used to countercheck the current login user;
    # Rory Saver, exp is an expired JWT standard field that automatically verifies when decoding
    # sub stored user id, with which each protected interface will be used to countercheck the current login user;
    # Rory Saver, exp is an expired JWT standard field that automatically verifies when decoding
    payload = {"sub": str(user.id), "role": user.role, "exp": expire_time,
               "credential_version": hashlib.sha256(user.password.encode()).hexdigest()}
    # Sign with key and HS256 algorithm in settings.py, which is the string you got at the front end
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(token: str | None = Header(default=None)) -> User:
    # Token, take it from the request. The front-end interceptor will be on every request.js
    if not token:
        # Token was tampered with, expired and not formatted. Unanimously treated as login failure
        raise CustomException("Session has expired, please log in again", "401")
    try:
        # Decoding checks both signatures and ext expiry times, either dropping an anomaly without passing
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})
        user_id = int(payload.get("sub"))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        # Token was tampered with, expired and not formatted. Unanimously treated as login failure
        raise CustomException("Session has expired, please log in again", "401")
    # Only ids in token, and one search for complete user information;
    # By the way, "token hasn't expired yet but accounts have been deleted or disabled."
    user = await User.get_or_none(id=user_id)
    if user is None or user.status != "NORMAL":
        raise CustomException("Account does not exist or has been disabled", "401")
    version = hashlib.sha256(user.password.encode()).hexdigest()
    if not hmac.compare_digest(str(payload.get("credential_version", "")), version):
        raise CustomException("Session has expired, please log in again", "401")
    return user


async def require_admin(token: str | None = Header(default=None)) -> User:
    # Token to get the user first, token to drop 401 when it's not working.
    user = await get_current_user(token)
    # Rejuvenate role, drop 403 when ordinary user accesss the management interface
    if user.role != "ADMIN":
        raise CustomException("No operation permissions", "403")
    return user
