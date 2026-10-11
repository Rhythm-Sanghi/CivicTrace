from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import User, UserRole
from app.schemas.all_schemas import UserCreate, UserPublic, Token
from app.core.security import verify_password, verify_dummy_password, get_password_hash, create_access_token
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
        action_key="auth_register"
    )

    # Prevent silent bcrypt truncation issues
    if len(user_in.password.encode("utf-8")) > 72:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password exceeds maximum allowed length of 72 bytes."
        )

    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
        )

    # Security Rule: Self-registered accounts ALWAYS default to CITIZEN role
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        role=UserRole.CITIZEN,
        is_active=True
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
    db: Session = Depends(get_db)
):
    check_rate_limit(
        request,
        max_requests=settings.RATE_LIMIT_LOGIN_MAX,
        window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        action_key="auth_login"
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
            detail="Account is deactivated. Contact an administrator."
        )

    access_token = create_access_token(subject=user.id)

    # Set secure HttpOnly session cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=(settings.ENVIRONMENT.lower() == "production"),
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout")
def logout(response: Response, current_user: Optional[User] = Depends(get_current_user_optional)):
    """Terminates session by clearing HttpOnly authentication cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Successfully signed out."}

@router.get("/me", response_model=UserPublic)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
