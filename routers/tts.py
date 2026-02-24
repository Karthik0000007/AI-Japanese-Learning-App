"""routers/tts.py — Offline Japanese text-to-speech via Piper."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from sqlmodel import SQLModel

from core.tts_piper import TTSError, synthesize

router = APIRouter(prefix="/api/tts", tags=["tts"])


class TTSRequest(SQLModel):
    text: str


@router.post("")
async def synthesize_speech(payload: TTSRequest) -> Response:
    """
    Synthesize *text* to WAV audio using Piper TTS.

    Returns audio/wav bytes directly — suitable for
    new Audio(URL.createObjectURL(blob)) in the frontend.
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty.")

    try:
        wav_bytes = await synthesize(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except TTSError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return Response(content=wav_bytes, media_type="audio/wav")
