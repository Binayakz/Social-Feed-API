import uuid

from pydantic import BaseModel, ConfigDict


class LikeUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str


class LikeActionResponse(BaseModel):
    liked: bool
    count: int


class LikeListResponse(BaseModel):
    count: int
    users: list[LikeUserResponse]
