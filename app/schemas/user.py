from uuid import UUID
from typing import Optional
import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=4, description="Tên người dùng phải trên 3 kí tự")
    phone: Optional[str] = Field(None, pattern=r'^\d{10}$')
    role: Optional[str] = "user"
    status: Optional[str] = "Active"


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ in hoa.')
        if not re.search(r'[a-z]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ thường.')
        if not re.search(r'\d', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 chữ số.')
        if not re.search(r'[\W_]', v):
            raise ValueError('Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt.')
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=4, description="Tên người dùng phải trên 3 kí tự")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r'^\d{10}$')
    role: Optional[str] = None
    status: Optional[str] = None


class UserResponse(UserBase):
    id: UUID

    class Config:
        from_attributes = True
