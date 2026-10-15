from pydantic import BaseModel, ConfigDict
from fastapi_users import schemas
import uuid
from typing import Optional
from datetime import datetime

class PostCreate(BaseModel):
    title: str
    content: str

class PostResponse(BaseModel):
    id: str
    user_id: str
    caption: Optional[str] = None
    url: str
    file_type: str
    file_name: str
    created_at: str
    is_owner: bool
    email: str

    model_config = ConfigDict(from_attributes=True)

class UserRead(schemas.BaseUser[uuid.UUID]):
    pass

class UserCreate(schemas.BaseUserCreate):
    pass

class UserUpdate(schemas.BaseUserUpdate):
    pass