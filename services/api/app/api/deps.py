from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
import hmac
from app.core.security import is_token_revoked
from app.models.entities import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False)

def _validate_csrf_if_cookie_auth(request: Request, is_cookie_auth: bool) -> None:
    """Enforces Double-Submit Cookie CSRF protection for cookie-authenticated mutating requests."""
    if not is_cookie_auth or not request:
        return

    # Non-mutating methods are safe from CSRF
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Exclude login and register from CSRF enforcement (login initiates session, register creates user)
    path = request.url.path
    if path.endswith("/auth/login") or path.endswith("/auth/register"):
        return

    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(settings.CSRF_HEADER_NAME)

    if not csrf_cookie or not csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF verification failed: missing CSRF token"
        )

    if not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF verification failed: token mismatch"
        )

def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    is_cookie_auth = False
    # Check Authorization Bearer header first; fallback to HttpOnly session cookie
    if not token and request:
        token = request.cookies.get("access_token")
        if token:
            is_cookie_auth = True

    if not token:
        return None

    # Check session revocation blocklist
    if is_token_revoked(token):
        return None

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            return None
    except jwt.PyJWTError:
        return None

    # Enforce CSRF defense if request is authenticated via browser session cookie
    _validate_csrf_if_cookie_auth(request, is_cookie_auth)

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user

def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def require_roles(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: role {current_user.role.value} does not have required permissions"
            )
        return current_user
    return role_checker
