from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Dict
import os
import hashlib
import json
import secrets
import threading
import jwt
import bcrypt
from app.core.config import settings

# In-memory session revocation store (token_hash -> expiration_timestamp)
# ARCHITECTURAL NOTE: This revocation store operates strictly within a single server process.
# It is designed for lightweight single-node and local deployments. It does NOT provide cluster-wide
# multi-process synchronization across multiple workers or persistence across process restarts.
# In a distributed multi-worker production cluster, a distributed backing store (such as Redis)
# or short-lived tokens with asymmetric key rotation must be configured.
_revoked_tokens_lock = threading.Lock()
_revoked_tokens: Dict[str, float] = {}
_revocation_file_loaded = False


def _get_revocation_file_path() -> str:
    path = os.path.join(settings.STORAGE_DIR, "revoked_tokens.json")
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    return path


def _sync_load_revoked_tokens() -> None:
    global _revocation_file_loaded
    if _revocation_file_loaded:
        return
    file_path = _get_revocation_file_path()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                now = datetime.now(timezone.utc).timestamp()
                for k, v in data.items():
                    if float(v) > now:
                        _revoked_tokens[k] = float(v)
        except Exception:
            pass
    _revocation_file_loaded = True


def _sync_persist_revoked_tokens() -> None:
    file_path = _get_revocation_file_path()
    try:
        now = datetime.now(timezone.utc).timestamp()
        active = {k: v for k, v in _revoked_tokens.items() if v > now}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(active, f)
    except Exception:
        pass


def revoke_token(token: str, expires_at: Optional[float] = None, db_session=None) -> None:
    """Revokes a JWT token so it cannot be reused prior to standard expiration.
    Persists to database table (RevokedToken) and synchronization cache across worker processes.
    """
    try:
        if expires_at is None:
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            expires_at = float(
                unverified_payload.get("exp", datetime.now(timezone.utc).timestamp() + 86400)
            )
    except Exception:
        expires_at = datetime.now(timezone.utc).timestamp() + 86400

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()

    # 1. Update in-memory and disk cache
    with _revoked_tokens_lock:
        _sync_load_revoked_tokens()
        expired_keys = [k for k, exp in _revoked_tokens.items() if exp <= now]
        for k in expired_keys:
            del _revoked_tokens[k]
        _revoked_tokens[token_hash] = expires_at
        _sync_persist_revoked_tokens()

    # 2. Persist to database if database session or connection is available
    try:
        from app.db.session import SessionLocal
        from app.models.entities import RevokedToken

        session = db_session if db_session else SessionLocal()
        close_session = db_session is None
        try:
            existing = (
                session.query(RevokedToken).filter(RevokedToken.token_hash == token_hash).first()
            )
            if not existing:
                record = RevokedToken(
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked_at=datetime.now(timezone.utc),
                )
                session.add(record)
                session.commit()
        except Exception:
            session.rollback()
        finally:
            if close_session:
                session.close()
    except Exception:
        pass


def is_token_revoked(token: str, db_session=None) -> bool:
    """Checks if a given JWT token has been placed on the revocation blocklist.
    Checks memory cache first, then disk cache, then database.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).timestamp()

    with _revoked_tokens_lock:
        _sync_load_revoked_tokens()
        exp = _revoked_tokens.get(token_hash)
        if exp is not None:
            if exp <= now:
                del _revoked_tokens[token_hash]
                _sync_persist_revoked_tokens()
                return False
            return True

    # Check database store
    try:
        from app.db.session import SessionLocal
        from app.models.entities import RevokedToken

        session = db_session if db_session else SessionLocal()
        close_session = db_session is None
        try:
            record = (
                session.query(RevokedToken).filter(RevokedToken.token_hash == token_hash).first()
            )
            if record:
                if record.expires_at <= now:
                    session.delete(record)
                    session.commit()
                    return False
                # Populate cache
                with _revoked_tokens_lock:
                    _revoked_tokens[token_hash] = record.expires_at
                return True
        except Exception:
            session.rollback()
        finally:
            if close_session:
                session.close()
    except Exception:
        pass

    return False


def clean_expired_revoked_tokens(db_session=None) -> int:
    """Prunes expired tokens from the database and memory store."""
    now = datetime.now(timezone.utc).timestamp()
    deleted_count = 0
    with _revoked_tokens_lock:
        expired = [k for k, exp in _revoked_tokens.items() if exp <= now]
        for k in expired:
            del _revoked_tokens[k]
        if expired:
            _sync_persist_revoked_tokens()

    try:
        from app.db.session import SessionLocal
        from app.models.entities import RevokedToken

        session = db_session if db_session else SessionLocal()
        close_session = db_session is None
        try:
            deleted_count = (
                session.query(RevokedToken).filter(RevokedToken.expires_at <= now).delete()
            )
            session.commit()
        except Exception:
            session.rollback()
        finally:
            if close_session:
                session.close()
    except Exception:
        pass
    return deleted_count


def reset_revoked_tokens_for_tests() -> None:
    """Resets the revoked token store for isolated test suites."""
    global _revocation_file_loaded
    with _revoked_tokens_lock:
        _revoked_tokens.clear()
        _revocation_file_loaded = True
        file_path = _get_revocation_file_path()
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    try:
        from app.db.session import SessionLocal
        from app.models.entities import RevokedToken

        session = SessionLocal()
        try:
            session.query(RevokedToken).delete()
            session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
    except Exception:
        pass


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
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(data: dict) -> str:
    """Produces deterministic serialized JSON for cryptographic hash chaining."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
