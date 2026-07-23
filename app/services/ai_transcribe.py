from typing import Any

import httpx

from app.core.config import settings


async def transcribe_audio(
    file_content: bytes,
    file_name: str,
    content_type: str | None = None,
) -> dict[str, Any]:
    if not settings.WHISPER_API_URL:
        raise RuntimeError("WHISPER_API_URL is not configured")

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
                settings.WHISPER_API_URL,
                files=files,
            )

        response.raise_for_status()
        result = response.json()

    except httpx.TimeoutException as exc:
        raise RuntimeError("Whisper API processing timed out") from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Whisper API returned status {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError(
            "Could not connect to the Whisper API"
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