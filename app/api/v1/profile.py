from fastapi import APIRouter

router = APIRouter()

@router.get("/me")
def get_profile():
    pass

@router.put("/me")
def update_profile():
    pass
