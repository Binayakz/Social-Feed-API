from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.rate_limit import ip_rate_limit
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import (
    authenticate_user,
    create_user,
    get_user_by_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            ip_rate_limit(
                scope="auth:register",
                limit=settings.RATE_LIMIT_AUTH_REGISTER_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_AUTH_REGISTER_WINDOW_SECONDS,
            )
        )
    ],
)
async def register(
        user_in: UserCreate,
        db: DBSession,
) -> UserResponse:
    existing_user = await get_user_by_email(db, user_in.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    user = await create_user(db, user_in)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            ip_rate_limit(
                scope="auth:login",
                limit=settings.RATE_LIMIT_AUTH_LOGIN_MAX_REQUESTS,
                window_seconds=settings.RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS,
            )
        )
    ],
)
async def login(
        credentials: LoginRequest,
        db: DBSession,
) -> TokenResponse:
    user = await authenticate_user(
        db,
        credentials.email,
        credentials.password,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_me(current_user: CurrentUser) -> UserResponse:
    return current_user
