from pydantic import BaseModel


class UploadedImageResponse(BaseModel):
    key: str
    url: str
    content_type: str
    size: int
