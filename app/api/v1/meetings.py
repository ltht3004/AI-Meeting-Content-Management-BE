from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def get_meetings():
    pass

@router.post("/")
def create_meeting():
    pass
