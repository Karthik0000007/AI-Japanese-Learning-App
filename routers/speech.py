"""routers/speech.py — Offline speech-to-text via OpenAI Whisper."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from sqlmodel import SQLModel

from core.whisper import WhisperError, check_whisper_available, transcribe_audio

SPEECH_UNAVAILABLE = (
    "Speech-to-text is not installed on this server. "
    "Install it with: pip install -r requirements-speech.txt"
)

router = APIRouter(prefix="/api/speech-to-text", tags=["speech"])


class SpeechResponse(SQLModel):
    """Response from speech-to-text transcription."""

    text: str
    """Transcribed text."""
    language: str
    """Detected language ('ja' or 'en')."""
    confidence: float
    """Confidence score (0.0-1.0)."""


@router.post("")
async def transcribe_speech(
    audio: UploadFile = File(...),
    language: str = None,
) -> SpeechResponse:
    """
    Transcribe audio file to text using Whisper.

    Args:
        audio: Audio file (WAV, MP3, FLAC, OGG, etc.)
        language: Optional language code ('ja', 'en', etc). Auto-detected if not provided.

    Returns:
        {
            "text": "transcribed text",
            "language": "ja" or "en",
            "confidence": 0.0-1.0
        }

    Raises:
        HTTPException 400: If audio is missing or corrupt.
        HTTPException 503: If Whisper is unavailable or transcription fails.
    """
    if not check_whisper_available():
        raise HTTPException(status_code=503, detail=SPEECH_UNAVAILABLE)

    if not audio or not audio.filename:
        raise HTTPException(status_code=400, detail="audio file is required.")

    # Read audio bytes
    try:
        audio_bytes = await audio.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read audio file: {exc}")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="audio file is empty.")

    # Transcribe
    try:
        result = await transcribe_audio(audio_bytes, language=language)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except WhisperError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return SpeechResponse(
        text=result["text"],
        language=result["language"],
        confidence=result["confidence"],
    )
