"""
core/tts_piper.py - Japanese text-to-speech helpers used by /api/tts.

Despite the historical module name, the working synthesis path for this app is
currently based on pyopenjtalk, which provides reliable offline Japanese speech
generation for kana/kanji input.

TTS is an OPTIONAL feature (see requirements-speech.txt). pyopenjtalk, numpy and
scipy are imported lazily inside the functions that need them, so the app starts
without them; the TTS endpoint then returns HTTP 503.
"""
from __future__ import annotations

import importlib.util
import io
import logging
from pathlib import Path
from typing import Any

import anyio

from core.language_detect import has_japanese

MAX_TEXT_LENGTH = 500
PROJECT_DICT_DIR = Path("data") / "open_jtalk_dic_utf_8-1.11"
TTS_PACKAGES = ("pyopenjtalk", "numpy", "scipy")
TTS_NOT_INSTALLED = (
    "Text-to-speech is not installed. "
    "Install it with: pip install -r requirements-speech.txt"
)

logger = logging.getLogger(__name__)


class TTSError(RuntimeError):
    """Raised when TTS fails or is not available."""


async def synthesize(text: str) -> bytes:
    """
    Convert Japanese text to WAV audio bytes.

    The app primarily synthesizes Japanese readings and kanji pronunciations, so
    we require Japanese characters and use pyopenjtalk for stable offline speech.
    """
    text = text.strip()
    if not text:
        raise ValueError("TTS text must not be empty.")
    if len(text) > MAX_TEXT_LENGTH:
        raise TTSError(
            f"Text length {len(text)} exceeds maximum {MAX_TEXT_LENGTH} characters."
        )
    if not has_japanese(text):
        raise TTSError("TTS currently supports Japanese text only.")

    pyopenjtalk = _pyopenjtalk_module()
    _configure_openjtalk_dict(pyopenjtalk)

    try:
        pcm_data, sample_rate = await anyio.to_thread.run_sync(
            lambda: pyopenjtalk.tts(text, speed=1.0)
        )
        return _pcm_to_wav(pcm_data, sample_rate)
    except Exception as exc:
        raise TTSError(f"Japanese TTS synthesis failed: {exc}") from exc


def check_tts_installed() -> bool:
    """Return True if the TTS packages are installed (instant, imports nothing)."""
    return all(importlib.util.find_spec(name) is not None for name in TTS_PACKAGES)


def check_piper_available() -> bool:
    """
    Backward-compatible health check for the app's TTS status indicator.

    Historically this checked Piper assets. The current working path is
    pyopenjtalk-based, so availability means the packages are installed and an
    OpenJTalk dictionary is already present (in data/ or inside the package).
    """
    if not check_tts_installed():
        return False

    if PROJECT_DICT_DIR.exists():
        return True

    package_dict = _get_package_openjtalk_dict_dir()
    return package_dict is not None and package_dict.exists()


def _pyopenjtalk_module() -> Any:
    """Import and return pyopenjtalk, or raise TTSError if TTS is not installed."""
    if not check_tts_installed():
        raise TTSError(TTS_NOT_INSTALLED)
    import pyopenjtalk

    return pyopenjtalk


def _configure_openjtalk_dict(pyopenjtalk: Any) -> None:
    """Point pyopenjtalk at a usable dictionary directory when one exists."""
    if PROJECT_DICT_DIR.exists():
        pyopenjtalk.OPEN_JTALK_DICT_DIR = str(PROJECT_DICT_DIR).encode("utf-8")
        return

    package_dict = _get_package_openjtalk_dict_dir()
    if package_dict is not None and package_dict.exists():
        pyopenjtalk.OPEN_JTALK_DICT_DIR = str(package_dict).encode("utf-8")
        return

    logger.info("OpenJTalk dictionary not found in project cache; pyopenjtalk will bootstrap it on first use.")


def _get_package_openjtalk_dict_dir() -> Path | None:
    """Locate the dictionary bundled inside the pyopenjtalk package, without importing it."""
    spec = importlib.util.find_spec("pyopenjtalk")
    if spec is None or not spec.submodule_search_locations:
        return None

    package_dir = Path(list(spec.submodule_search_locations)[0]).resolve()
    return package_dir / "open_jtalk_dic_utf_8-1.11"


def _pcm_to_wav(pcm_data: Any, sample_rate: int) -> bytes:
    """Convert float/int PCM audio to WAV bytes."""
    import numpy as np
    from scipy.io import wavfile

    pcm = np.asarray(pcm_data)

    if np.issubdtype(pcm.dtype, np.floating):
        max_abs = float(np.max(np.abs(pcm))) if pcm.size else 0.0
        if max_abs > 1.0:
            pcm = pcm / max_abs
        pcm = np.clip(pcm, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)
    else:
        pcm = pcm.astype(np.int16)

    wav_buffer = io.BytesIO()
    wavfile.write(wav_buffer, sample_rate, pcm)
    wav_buffer.seek(0)
    return wav_buffer.read()
