from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    locale: Literal["en", "fa"] = "en"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(EmailTokenRequest):
    new_password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    locale: Literal["en", "fa"]
    role: Literal["user", "admin"]


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class RegisterResponse(BaseModel):
    message: Literal["Registration request accepted"] = "Registration request accepted"


class MeResponse(UserResponse):
    email_verified: bool
