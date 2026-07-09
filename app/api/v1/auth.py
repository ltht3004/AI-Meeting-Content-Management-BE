from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate

router = APIRouter()


class UserLogin(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    existed_user = db.query(User).filter(User.email == user.email).first()

    if existed_user:
        raise HTTPException(status_code=400, detail="Email đã tồn tại")

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password=user.password,
        role=user.role or "user",
        status=user.status or "Active"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Email không tồn tại")

    if db_user.password != user.password:
        raise HTTPException(status_code=400, detail="Mật khẩu không đúng")

    if db_user.status == "Unactive":
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa")

    return {
        "message": "Đăng nhập thành công",
        "user_id": db_user.id,
        "full_name": db_user.full_name,
        "email": db_user.email,
        "phone": db_user.phone,
        "role": db_user.role,
        "status": db_user.status
    }