"""Authentication request and response DTOs."""

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


class AuthSessionResponse(BaseModel):
    authenticated: bool
    role: Literal["admin"] | None = None
    username: str | None = None
    csrf_token: str | None = None
    management_enabled: bool = False


class AuthMessageResponse(BaseModel):
    message: str
