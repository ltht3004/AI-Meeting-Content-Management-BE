from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from app.core.config import settings


def _require_storage_config() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase Storage is not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )


def _normalize_supabase_url() -> str:
    return settings.SUPABASE_URL.rstrip("/")


def upload_file_to_storage(
    *,
    contents: bytes,
    object_path: str,
    content_type: str
) -> str:
    _require_storage_config()

    bucket = settings.SUPABASE_STORAGE_BUCKET
    encoded_path = quote(object_path, safe="/")
    storage_url = _normalize_supabase_url()
    upload_url = f"{storage_url}/storage/v1/object/{bucket}/{encoded_path}"

    request = Request(
        upload_url,
        data=contents,
        method="POST",
        headers={
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": content_type,
            "x-upsert": "true",
        }
    )

    try:
        with urlopen(request, timeout=60) as response:
            if response.status not in (200, 201):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Cannot upload recording to Supabase Storage."
                )
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase Storage upload failed: {error_body or exc.reason}"
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot connect to Supabase Storage: {exc.reason}"
        ) from exc

    return f"{storage_url}/storage/v1/object/public/{bucket}/{encoded_path}"


def build_recording_storage_path(meeting_id: str, file_name: str) -> str:
    safe_name = Path(file_name).name.replace(" ", "_")
    return f"recordings/{meeting_id}/{safe_name}"


def extract_storage_path(file_url: str) -> str | None:
    if not file_url:
        return None

    marker = f"/storage/v1/object/public/{settings.SUPABASE_STORAGE_BUCKET}/"
    parsed_path = urlparse(file_url).path

    if marker not in parsed_path:
        return None

    return unquote(parsed_path.split(marker, 1)[1])


def delete_file_from_storage(file_url: str) -> None:
    _require_storage_config()

    object_path = extract_storage_path(file_url)
    if not object_path:
        return

    bucket = settings.SUPABASE_STORAGE_BUCKET
    encoded_path = quote(object_path, safe="/")
    storage_url = _normalize_supabase_url()
    delete_url = f"{storage_url}/storage/v1/object/{bucket}/{encoded_path}"

    request = Request(
        delete_url,
        method="DELETE",
        headers={
            "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        }
    )

    try:
        with urlopen(request, timeout=60) as response:
            if response.status not in (200, 204):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Cannot delete recording from Supabase Storage."
                )
    except HTTPError as exc:
        if exc.code == 404:
            return

        error_body = exc.read().decode("utf-8", errors="ignore")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Supabase Storage delete failed: {error_body or exc.reason}"
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot connect to Supabase Storage: {exc.reason}"
        ) from exc
