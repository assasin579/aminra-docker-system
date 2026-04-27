import re
from passlib.context import CryptContext

_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _ctx.verify(plain, hashed)


class WeakPasswordError(ValueError):
    """Raised when a password fails the strength requirements."""


def validate_password_strength(password: str) -> None:
    """Project-wide password rules: ≥10 chars, 1 upper, 1 lower, 1 digit.

    Raises WeakPasswordError with a Vietnamese user-facing message on failure.
    """
    if len(password) < 10:
        raise WeakPasswordError("Mật khẩu phải có ít nhất 10 ký tự")
    if not re.search(r"[A-Z]", password):
        raise WeakPasswordError("Mật khẩu phải có ít nhất 1 chữ hoa")
    if not re.search(r"[a-z]", password):
        raise WeakPasswordError("Mật khẩu phải có ít nhất 1 chữ thường")
    if not re.search(r"\d", password):
        raise WeakPasswordError("Mật khẩu phải có ít nhất 1 chữ số")
