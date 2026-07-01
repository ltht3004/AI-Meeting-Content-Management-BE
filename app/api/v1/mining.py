from fastapi import APIRouter

router = APIRouter()

@router.get("/transcript/{meeting_id}")
def get_transcript():
    pass

@router.get("/summary/{meeting_id}")
def get_summary():
    pass

@router.get("/export/{meeting_id}/{format}")
def export_meeting():
    pass
