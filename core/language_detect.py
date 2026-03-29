"""
core/language_detect.py — Fast language detection using character ranges.

Detects Japanese vs English by checking Unicode character ranges:
- Hiragana: U+3040..U+309F
- Katakana: U+30A0..U+30FF
- Kanji: U+4E00..U+9FFF
- CJK Unified Ideographs

No external API or model required — pure regex on input text.
"""
from __future__ import annotations


JAPANESE_CHAR_PATTERN = r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]"
"""Regex pattern matching hiragana, katakana, or kanji."""


def detect_language(text: str) -> str:
    """
    Detect language of text (Japanese vs English).

    Strategy:
    - If text contains Japanese characters (hiragana/katakana/kanji) → "ja"
    - Otherwise → "en"

    Args:
        text: Input text to classify.

    Returns:
        "ja" or "en"
    """
    import re

    if not text:
        return "en"  # Default to English for empty text

    # Check if any Japanese character exists
    if re.search(JAPANESE_CHAR_PATTERN, text):
        return "ja"

    return "en"


def has_japanese(text: str) -> bool:
    """
    Quick check if text contains any Japanese characters.

    Args:
        text: Input text.

    Returns:
        True if text contains hiragana, katakana, or kanji.
    """
    import re

    if not text:
        return False

    return bool(re.search(JAPANESE_CHAR_PATTERN, text))
