from fastapi import APIRouter

from app.api.routes import auth_router
from app.api.routes import post_router
from app.api.routes import comment_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(post_router)
api_router.include_router(comment_router)
