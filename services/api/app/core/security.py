from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import hashlib
import json
import jwt
import bcrypt
from app.core.config import settings

# Precomputed bcrypt hash of a random token to maintain constant-time login responses
# and prevent timing-based user enumeration attacks.
_DUMMY_BCRYPT_HASH = "$2b$12$e8k6m7aU.d2sV8Qj.Q1dpuY4O.W8kQ0x7vV0B5Rz9I.q0.O5B/r2m"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pw_bytes = plain_password.encode("utf-8")
        if len(pw_bytes) > 72:
            return False
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False

def verify_dummy_password(plain_password: str) -> None:
    """Consumes CPU time equivalent to verify_password to mitigate account existence timing leaks."""
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        bcrypt.checkpw(pw_bytes, _DUMMY_BCRYPT_HASH.encode("utf-8"))
    except Exception:
        pass

def get_password_hash(password: str) -> str:
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) > 72:
        raise ValueError("Password exceeds maximum allowed length of 72 bytes.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_json(data: dict) -> str:
    """Produces deterministic serialized JSON for cryptographic hash chaining."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
