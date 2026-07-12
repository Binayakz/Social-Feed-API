import uuid
from functools import lru_cache
from pathlib import Path

import boto3
from fastapi import HTTPException, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.schemas.upload import UploadedImageResponse

_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@lru_cache
def get_s3_client():
    client_kwargs = {
        "service_name": "s3",
        "region_name": settings.AWS_REGION,
    }
    if settings.S3_ENDPOINT_URL:
        client_kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    if settings.AWS_SESSION_TOKEN:
        client_kwargs["aws_session_token"] = settings.AWS_SESSION_TOKEN
    return boto3.client(**client_kwargs)


def _measure_size(file_obj) -> int:
    file_obj.seek(0, 2)
    size = file_obj.tell()
    file_obj.seek(0)
    return size


def _build_key(user_id: uuid.UUID, filename: str | None, content_type: str) -> str:
    fallback_ext = _ALLOWED_IMAGE_TYPES[content_type]
    suffix = Path(filename or "").suffix.lower() or fallback_ext
    return f"{settings.S3_OBJECT_PREFIX.rstrip('/')}/{user_id}/{uuid.uuid4().hex}{suffix}"


def _upload_fileobj(file_obj, key: str, content_type: str) -> None:
    get_s3_client().upload_fileobj(
        file_obj,
        settings.S3_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )


async def upload_post_image(*, user_id: uuid.UUID, file: UploadFile) -> UploadedImageResponse:
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type",
        )

    size = await run_in_threadpool(_measure_size, file.file)
    if size <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large",
        )

    key = _build_key(user_id, file.filename, content_type)
    await run_in_threadpool(_upload_fileobj, file.file, key, content_type)

    return UploadedImageResponse(
        key=key,
        url=f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}",
        content_type=content_type,
        size=size,
    )
