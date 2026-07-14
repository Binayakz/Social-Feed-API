from fastapi import APIRouter

from app.api.routes import (
    auth_router,
    comment_router,
    like_router,
    post_router,
    upload_router,
    user_router,
)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(post_router)
api_router.include_router(comment_router)
api_router.include_router(like_router)
api_router.include_router(upload_router)
api_router.include_router(user_router)
