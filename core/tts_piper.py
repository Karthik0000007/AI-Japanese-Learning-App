"""
core/tts_piper.py — Offline Japanese text-to-speech via Piper TTS.

Piper is invoked as a subprocess: text is written to stdin, WAV audio bytes
are read from stdout.  This avoids the overhead of a persistent process while
keeping the FastAPI event loop non-blocking (asyncio.subprocess).

Voice model: ja_JP-kokoro-medium.onnx  (~80 MB)
  Download: https://huggingface.co/rhasspy/piper-voices/tree/main/ja/ja_JP/kokoro/medium
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from config import settings

MAX_TEXT_LENGTH = 500  # Characters — enforced before spawning subprocess


class TTSError(RuntimeError):
    """Raised when Piper fails or is not available."""


async def synthesize(text: str) -> bytes:
    """
    Convert *text* to WAV audio bytes using the Piper TTS subprocess.

    Args:
        text: Japanese (or any supported) text to synthesize.

    Returns:
        Raw WAV file bytes suitable for an audio/wav HTTP response.

    Raises:
        TTSError: If Piper binary is missing, text is too long, or Piper exits non-zero.
        ValueError: If text is empty.
    """
    text = text.strip()
    if not text:
        raise ValueError("TTS text must not be empty.")
    if len(text) > MAX_TEXT_LENGTH:
        raise TTSError(
            f"Text length {len(text)} exceeds maximum {MAX_TEXT_LENGTH} characters."
        )

    binary = _resolve_binary()
    model_path = _resolve_model()

    cmd = [
        binary,
        "--model", str(model_path),
        "--output_raw",  # PCM output — we add the WAV header ourselves
        "--output-raw",  # some versions use hyphens
    ]

    # Use --output_file - to write WAV to stdout (Piper >= 1.2)
    cmd = [
        binary,
        "--model", str(model_path),
        "--output_file", "-",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_data, stderr_data = await proc.communicate(input=text.encode("utf-8"))
    except FileNotFoundError:
        raise TTSError(
            f"Piper binary not found: '{binary}'. "
            "Install it and set PIPER_BINARY in .env, or run: python tools/setup.py"
        )
    except Exception as exc:
        raise TTSError(f"Failed to run Piper subprocess: {exc}") from exc

    if proc.returncode != 0:
        stderr_text = stderr_data.decode("utf-8", errors="replace").strip()
        raise TTSError(
            f"Piper exited with code {proc.returncode}. Stderr: {stderr_text}"
        )

    if not stdout_data:
        raise TTSError("Piper produced no audio output.")

    return stdout_data


def check_piper_available() -> bool:
    """Return True if both the Piper binary and model file exist."""
    try:
        _resolve_binary()
        _resolve_model()
        return True
    except TTSError:
        return False


# ─── Private helpers ──────────────────────────────────────────────────────────

def _resolve_binary() -> str:
    """Return the Piper binary path, raising TTSError if not found."""
    binary = settings.piper_binary
    # If it's just "piper", check PATH
    if not os.path.isabs(binary):
        found = shutil.which(binary)
        if found:
            return found
        raise TTSError(
            f"Piper binary '{binary}' not found in PATH. "
            "Set PIPER_BINARY in .env to the absolute path."
        )
    if not Path(binary).exists():
        raise TTSError(f"Piper binary not found at configured path: {binary}")
    return binary


def _resolve_model() -> Path:
    """Return the resolved model path, raising TTSError if not found."""
    model = Path(settings.piper_model_path)
    if not model.is_absolute():
        model = Path.cwd() / model
    if not model.exists():
        raise TTSError(
            f"Piper voice model not found: {model}. "
            "Run: python tools/setup.py  (downloads the model automatically)"
        )
    return model
