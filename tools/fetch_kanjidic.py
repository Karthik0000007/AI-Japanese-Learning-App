"""
tools/fetch_kanjidic.py — Download and parse KANJIDIC2.xml into JSON.

Cached output: data/kanjidic_parsed.json
Run standalone: python tools/fetch_kanjidic.py
"""
from __future__ import annotations

import gzip
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from lxml import etree

KANJIDIC_URL = "http://www.edrdg.org/kanjidic/kanjidic2.xml.gz"
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_GZ = DATA_DIR / "kanjidic2.xml.gz"
OUTPUT_JSON = DATA_DIR / "kanjidic_parsed.json"

# JLPT grade mapping in KANJIDIC2: grade 8 = Jōyō pre-JLPT
_JLPT_FROM_KANJIDIC_TAG: dict[str, str] = {
    "jlpt1": "N1",
    "jlpt2": "N2",
    "jlpt3": "N3",
    "jlpt4": "N4",  # N4+N5 used to be merged as "level 4" in old JLPT
}


def download_kanjidic(force: bool = False) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_GZ.exists() and not force:
        print(f"[KANJIDIC] Using cached file: {CACHE_GZ}")
        return CACHE_GZ
    print(f"[KANJIDIC] Downloading from {KANJIDIC_URL} …")
    urllib.request.urlretrieve(KANJIDIC_URL, CACHE_GZ)
    print(f"[KANJIDIC] Saved ({CACHE_GZ.stat().st_size / 1e6:.1f} MB)")
    return CACHE_GZ


def parse_kanjidic(gz_path: Path) -> list[dict[str, Any]]:
    print("[KANJIDIC] Parsing XML…")
    entries: list[dict[str, Any]] = []

    with gzip.open(gz_path, "rb") as f:
        tree = etree.parse(f)

    for char_elem in tree.findall("character"):
        # Kanji literal
        literal_elem = char_elem.find("literal")
        if literal_elem is None or not literal_elem.text:
            continue
        character = literal_elem.text

        # Readings
        on_yomi: list[str] = []
        kun_yomi: list[str] = []
        for reading in char_elem.findall("reading_meaning/rmgroup/reading"):
            r_type = reading.get("r_type", "")
            if r_type == "ja_on":
                on_yomi.append(reading.text)
            elif r_type == "ja_kun":
                kun_yomi.append(reading.text)

        # Meanings (English only)
        meanings: list[str] = [
            m.text
            for m in char_elem.findall("reading_meaning/rmgroup/meaning")
            if m.text and not m.get("m_lang")  # no lang attr = English
        ]

        # Stroke count
        stroke_elem = char_elem.find("misc/stroke_count")
        stroke_count = int(stroke_elem.text) if stroke_elem is not None and stroke_elem.text else 0

        # JLPT level tag
        jlpt_level: str | None = None
        for tag_elem in char_elem.findall("misc/jlpt"):
            raw = (tag_elem.text or "").strip().lower()
            if raw:
                # New-style "N1"–"N4" or old-style "1"–"4"
                if raw.startswith("n"):
                    jlpt_level = raw.upper()
                elif raw in ("1", "2", "3", "4"):
                    jlpt_level = f"N{raw}"

        # Frequency rank
        freq_elem = char_elem.find("misc/freq")
        freq_rank = int(freq_elem.text) if freq_elem is not None and freq_elem.text else None

        if not meanings:
            continue

        entries.append({
            "character": character,
            "on_yomi": on_yomi,
            "kun_yomi": kun_yomi,
            "meaning": meanings,
            "stroke_count": stroke_count,
            "jlpt_level": jlpt_level,
            "freq_rank": freq_rank,
            "example_word": None,
            "example_sentence": None,
        })

    print(f"[KANJIDIC] Parsed {len(entries)} kanji entries.")
    return entries


def run(force_download: bool = False) -> list[dict[str, Any]]:
    gz = download_kanjidic(force=force_download)
    entries = parse_kanjidic(gz)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"[KANJIDIC] Wrote {len(entries)} entries → {OUTPUT_JSON}")
    return entries


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    run(force_download=args.force)
