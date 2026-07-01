from fastapi import APIRouter

router = APIRouter()

@router.post("/upload/{meeting_id}")
def upload_recording():
    pass
