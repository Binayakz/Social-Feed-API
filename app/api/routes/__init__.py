from app.api.routes.auth import router as auth_router
from app.api.routes.post import router as post_router
from app.api.routes.comment import router as comment_router
from app.api.routes.like import router as like_router
from app.api.routes.upload import router as upload_router

__all__ = ["auth_router", "post_router", "comment_router", "like_router", "upload_router"]
