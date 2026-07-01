from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_users():
    pass

@router.get("/{user_id}")
def get_user():
    pass
