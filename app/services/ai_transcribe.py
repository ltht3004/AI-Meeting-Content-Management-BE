from typing import Any
from urllib.parse import urljoin

import httpx

from app.core.config import settings


def get_whisper_endpoint() -> str:
    url = settings.WHISPER_API_URL.strip()
    if not url:
        raise RuntimeError("WHISPER_API_URL is not configured")

    if url.rstrip("/").endswith("/api/transcribe"):
        return url

    return urljoin(f"{url.rstrip('/')}/", "api/transcribe")


async def transcribe_audio(
    file_content: bytes,
    file_name: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    whisper_endpoint = get_whisper_endpoint()

    files = {
        "file": (
            file_name,
            file_content,
            content_type or "application/octet-stream",
        )
    }

    try:
        async with httpx.AsyncClient(timeout=900.0) as client:
            response = await client.post(
                whisper_endpoint,
                files=files,
            )

        response.raise_for_status()
        result = response.json()

    except httpx.TimeoutException as exc:
        raise RuntimeError(
            f"Whisper API processing timed out: {whisper_endpoint}"
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Whisper API returned status {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not connect to the Whisper API: {whisper_endpoint}. "
            f"Error: {exc}"
        ) from exc

    except ValueError as exc:
        raise RuntimeError(
            "Whisper API returned invalid JSON"
        ) from exc

    transcript_text = result.get("text")

    if transcript_text is None:
        raise RuntimeError(
            "Whisper API did not return transcript text"
        )

    return {
        "text": transcript_text,
        "language": result.get("language"),
    }
