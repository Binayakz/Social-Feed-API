import uuid
import warnings
from functools import lru_cache
from io import BytesIO

import boto3
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.schemas.upload import UploadedImageResponse

_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": {
        "extension": ".jpg",
        "pil_formats": {"JPEG"},
    },
    "image/png": {
        "extension": ".png",
        "pil_formats": {"PNG"},
    },
    "image/webp": {
        "extension": ".webp",
        "pil_formats": {"WEBP"},
    },
}

_OPTIONAL_DECLARED_TYPES = {"", "application/octet-stream"}


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


def _detect_content_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"

    return None


async def _read_limited_bytes(file: UploadFile) -> bytes:
    data = await file.read(settings.MAX_IMAGE_UPLOAD_BYTES + 1)

    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    if len(data) > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too large",
        )

    return data


def _validate_declared_content_type(declared_content_type: str) -> None:
    if (
            declared_content_type
            and declared_content_type not in _OPTIONAL_DECLARED_TYPES
            and declared_content_type not in _ALLOWED_IMAGE_TYPES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image type. Allowed types: JPEG, PNG, WEBP.",
        )


def _validate_detected_content_type(
        declared_content_type: str,
        detected_content_type: str | None,
) -> str:
    if detected_content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or unsupported image file.",
        )

    if (
            declared_content_type not in _OPTIONAL_DECLARED_TYPES
            and declared_content_type != detected_content_type
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file content does not match the declared image type.",
        )

    return detected_content_type


def _validate_image_bytes(data: bytes, detected_content_type: str) -> None:
    expected_formats = _ALLOWED_IMAGE_TYPES[detected_content_type]["pil_formats"]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(data)) as image:
                image.verify()

            with Image.open(BytesIO(data)) as image:
                if image.format not in expected_formats:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid image format.",
                    )

                width, height = image.size
                if width <= 0 or height <= 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid image dimensions.",
                    )

                if width * height > settings.MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Image dimensions are too large.",
                    )

                image.load()
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file.",
        )
    except (Image.DecompressionBombWarning, Image.DecompressionBombError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image dimensions are too large.",
        )


def _build_key(user_id: uuid.UUID, content_type: str) -> str:
    extension = _ALLOWED_IMAGE_TYPES[content_type]["extension"]
    return f"{settings.S3_OBJECT_PREFIX.rstrip('/')}/{user_id}/{uuid.uuid4().hex}{extension}"


def _upload_bytes(data: bytes, key: str, content_type: str) -> None:
    get_s3_client().upload_fileobj(
        BytesIO(data),
        settings.S3_BUCKET_NAME,
        key,
        ExtraArgs={
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )


async def upload_post_image(*, user_id: uuid.UUID, file: UploadFile) -> UploadedImageResponse:
    declared_content_type = (file.content_type or "").lower().strip()
    _validate_declared_content_type(declared_content_type)

    data = await _read_limited_bytes(file)
    detected_content_type = _detect_content_type(data)
    safe_content_type = _validate_detected_content_type(
        declared_content_type,
        detected_content_type,
    )

    await run_in_threadpool(_validate_image_bytes, data, safe_content_type)

    key = _build_key(user_id, safe_content_type)
    await run_in_threadpool(_upload_bytes, data, key, safe_content_type)

    return UploadedImageResponse(
        key=key,
        url=f"{settings.S3_PUBLIC_BASE_URL.rstrip('/')}/{key}",
        content_type=safe_content_type,
        size=len(data),
    )
