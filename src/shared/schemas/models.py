from typing import Literal

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=63)
    repository_url: str = Field(min_length=1)
    port: int = Field(default=8000, ge=1, le=65535)


class ProjectResponse(BaseModel):
    id: str
    name: str
    repository_url: str
    status: Literal["READY"]
    url: str
    image: str
