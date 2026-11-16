"""Salted PBKDF2 password storage, using the Python standard library."""
import hashlib
import hmac
import secrets

PREFIX = "pbkdf2_sha256$"
def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600000).hex()
    return f"{PREFIX}600000${salt}${digest}"

def verify_password(password, encoded):
    if not password or not encoded.startswith(PREFIX):
        return False
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False

async def migrate_passwords():
    from models import User
    for user in await User.all():
        if not user.password.startswith(PREFIX):
            await User.filter(id=user.id).update(password=hash_password(user.password))
