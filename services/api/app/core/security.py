from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Dict
import hashlib
import json
import secrets
import threading
import jwt
import bcrypt
from app.core.config import settings

# Thread-safe in-memory session revocation store (token_signature -> expiration_timestamp)
_revoked_tokens_lock = threading.Lock()
_revoked_tokens: Dict[str, float] = {}

def revoke_token(token: str, expires_at: Optional[float] = None) -> None:
    """Revokes a JWT token so it cannot be reused even prior to standard expiration."""
    try:
        # Extract expiration if not passed directly
        if expires_at is None:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            expires_at = float(unverified_payload.get("exp", datetime.now(timezone.utc).timestamp() + 86400))

        # Token key: sha256 hash of token to save memory and avoid storing raw token
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).timestamp()

        with _revoked_tokens_lock:
            # Purge expired entries to prevent unbounded memory growth
            expired_keys = [k for k, exp in _revoked_tokens.items() if exp <= now]
            for k in expired_keys:
                del _revoked_tokens[k]
            _revoked_tokens[token_hash] = expires_at
    except Exception:
        # Fallback hash storage for malformed tokens
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with _revoked_tokens_lock:
            _revoked_tokens[token_hash] = datetime.now(timezone.utc).timestamp() + 86400

def is_token_revoked(token: str) -> bool:
    """Checks if a given JWT token has been placed on the revocation blocklist."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()
    with _revoked_tokens_lock:
        exp = _revoked_tokens.get(token_hash)
        if exp is None:
            return False
        if exp <= now:
            del _revoked_tokens[token_hash]
            return False
        return True

def reset_revoked_tokens_for_tests() -> None:
    """Resets the revoked token store for isolated test suites."""
    with _revoked_tokens_lock:
        _revoked_tokens.clear()

def generate_csrf_token() -> str:
    """Generates a cryptographically secure random token for Double Submit CSRF defense."""
    return secrets.token_urlsafe(32)


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
