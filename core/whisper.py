"""
core/whisper.py — Offline speech-to-text via OpenAI Whisper.

Whisper is an OPTIONAL dependency (see requirements-speech.txt). It is imported
lazily inside _get_model(), so the app starts and runs without it; the speech
endpoint then returns HTTP 503. The model is loaded on first use and cached.

Model: "base" (74MB)
  - Accuracy: ~74% WER
  - Speed: ~10-20s per minute of audio on CPU
  - Language: Auto-detected, but focuses on Japanese/English
"""
from __future__ import annotations

import importlib.util
import logging
import os
import tempfile
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)

_model_cache: Optional[Any] = None


class WhisperError(RuntimeError):
    """Raised when Whisper fails or is not available."""


async def transcribe_audio(audio_bytes: bytes, language: Optional[str] = None) -> dict:
    """
    Transcribe audio bytes to text using OpenAI Whisper.

    Args:
        audio_bytes: Raw audio file bytes (WAV, MP3, FLAC, etc.)
        language: Optional language code ("ja", "en", etc). If None, auto-detect.

    Returns:
        {
            "text": "transcribed text",
            "language": "ja" or "en" (detected),
            "confidence": 0.0-1.0 (estimated from Whisper's log probs)
        }

    Raises:
        WhisperError: If audio is corrupt or Whisper fails.
        ValueError: If audio is empty.
    """
    if not audio_bytes:
        raise ValueError("Audio bytes must not be empty.")

    try:
        model = _get_model()
    except Exception as exc:
        raise WhisperError(
            f"Failed to load Whisper model '{settings.whisper_model}'. "
            f"Check that torch and openai-whisper are installed. Error: {exc}"
        ) from exc

    # Load audio from bytes via a temporary file.
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        audio = _whisper_module().load_audio(tmp_path)
    except Exception as exc:
        raise WhisperError(f"Failed to load audio data: {exc}") from exc
    finally:
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # Transcribe
    try:
        result = model.transcribe(
            audio,
            language=language,  # None = auto-detect
            fp16=False,  # Use full precision (safer on CPU)
        )
    except Exception as exc:
        raise WhisperError(f"Whisper transcription failed: {exc}") from exc

    # Extract detected language and text
    detected_language = result.get("language", "unknown")
    text = result.get("text", "").strip()

    if not text:
        logger.warning(f"Whisper returned empty text for language={language}")
        raise WhisperError("Whisper transcribed no text from audio.")

    # Estimate confidence from Whisper's internal log probs
    # Whisper doesn't expose confidence directly; approximate from segment scores
    confidence = _estimate_confidence(result)

    return {
        "text": text,
        "language": detected_language,
        "confidence": confidence,
    }


def check_whisper_available() -> bool:
    """
    Return True if the openai-whisper package is installed.

    Uses find_spec so the check is instant: it neither imports torch nor loads
    (or downloads) the model, which keeps /api/health fast.
    """
    return importlib.util.find_spec("whisper") is not None


# ─────────────────────────────────────────────────────────────────────────────


def _get_model() -> Any:
    """
    Get or load the Whisper model (lazy singleton).

    Model is cached in memory after first load to avoid repeated I/O.
    """
    global _model_cache

    if _model_cache is not None:
        return _model_cache

    whisper = _whisper_module()

    logger.info(
        f"Loading Whisper model '{settings.whisper_model}' on device '{settings.whisper_device}'..."
    )
    try:
        _model_cache = whisper.load_model(
            settings.whisper_model,
            device=settings.whisper_device,
        )
        logger.info(f"Whisper model '{settings.whisper_model}' loaded successfully.")
        return _model_cache
    except Exception as exc:
        logger.error(f"Failed to load Whisper model: {exc}")
        raise


def _whisper_module() -> Any:
    """Import and return the whisper package, or raise WhisperError if missing."""
    try:
        import whisper
    except ImportError as exc:
        raise WhisperError(
            "Speech-to-text is not installed. "
            "Install it with: pip install -r requirements-speech.txt"
        ) from exc
    return whisper


def _estimate_confidence(result: dict) -> float:
    """
    Estimate confidence score (0.0-1.0) from Whisper result.

    Whisper doesn't expose raw confidence, so we approximate from:
    - Average log probability of segments
    - Number of segments with high probabilities
    """
    segments = result.get("segments", [])
    if not segments:
        return 0.5

    # Whisper stores log probabilities; convert to rough confidence
    # Typical log probs range from -0.2 (high conf) to -2.0 (low conf)
    log_probs = [s.get("avg_logprob", -1.0) for s in segments]
    avg_log_prob = sum(log_probs) / len(log_probs) if log_probs else -1.0

    # Map log probs to confidence: -0.2 -> 0.9, -2.0 -> 0.1
    # Rough formula: confidence = (log_prob + 2) / 2, clamped to [0, 1]
    confidence = max(0.0, min(1.0, (avg_log_prob + 2.0) / 2.0))

    return confidence
