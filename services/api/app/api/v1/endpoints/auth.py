from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User, UserRole
from app.schemas.all_schemas import UserCreate, UserPublic, Token
from app.core.security import (
    verify_password,
    verify_dummy_password,
    get_password_hash,
    create_access_token,
    generate_csrf_token,
    revoke_token,
)
from app.core.rate_limiter import check_rate_limit
from app.core.config import settings
from app.api.deps import get_current_user, get_current_user_optional

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_REGISTER_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="auth_register",
    )

    # Prevent silent bcrypt truncation issues
    if len(user_in.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password exceeds maximum allowed length of 72 bytes.",
        )

    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Security Rule: Self-registered accounts ALWAYS default to CITIZEN role
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        role=UserRole.CITIZEN,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_LOGIN_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="auth_login",
    )

    user = db.query(User).filter(User.email == form_data.username).first()

    # Mitigate timing-based account enumeration: consume identical CPU time if user is absent
    if not user:
        verify_dummy_password(form_data.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact an administrator.",
        )

    access_token = create_access_token(subject=user.id)
    csrf_token = generate_csrf_token()

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT.lower() == "production"),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Set readable CSRF cookie for Double-Submit pattern (non-HttpOnly so client JS can read and send in header)
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=(settings.ENVIRONMENT.lower() == "production"),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

    # Check whether client explicitly requested bearer token output via query param (for CLI/scripts).
    # By default in browser cookie flows, access_token is NEVER exposed to client-side JavaScript.
    # Accept header inference has been removed: bearer delivery strictly requires an explicit parameter.
    include_token = (
        request.query_params.get("include_token") == "true"
        or request.query_params.get("format") == "token"
    )

    return {
        "access_token": access_token if include_token else None,
        "token_type": "bearer" if include_token else "cookie",
        "user": user,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Terminates session by revoking the active token and clearing cookies."""
    # Revoke the session token (from Authorization header or access_token cookie)
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get("access_token")

    if token:
        revoke_token(token, db_session=db)

    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key=settings.CSRF_COOKIE_NAME, path="/")
    return {"message": "Successfully signed out."}


@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/users/{user_id}/verify-identity", response_model=UserPublic)
def verify_user_identity(
    user_id: str,
    provider: str = Query("MUNICIPAL_VERIFIED_ENROLLMENT", min_length=3, max_length=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Authorized Administrator endpoint to enroll a citizen with verified identity assurance.
    Ordinary self-registration CANNOT set verified identity status.
    """
    if current_user.role != UserRole.ADMINISTRATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only system administrators can enroll verified identity assurance.",
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target user not found.",
        )

    target_user.is_identity_verified = True
    target_user.identity_provider = provider
    db.commit()
    db.refresh(target_user)
    return target_user
