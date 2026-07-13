from fastapi import APIRouter
from app.api.v1 import auth, profile, users, meetings, recordings, mining, dashboard

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(meetings.router, prefix="/meetings", tags=["meetings"])
api_router.include_router(recordings.router, prefix="/recordings", tags=["recordings"])
api_router.include_router(mining.router, prefix="/mining", tags=["mining"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
