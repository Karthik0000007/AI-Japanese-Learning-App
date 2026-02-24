"""
tools/fetch_jmdict.py — Download and parse JMdict_e.xml into JSON.

Cached output: data/jmdict_parsed.json
Run standalone: python tools/fetch_jmdict.py
"""
from __future__ import annotations

import gzip
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from lxml import etree

JMDICT_URL = "http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz"
DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_GZ = DATA_DIR / "JMdict_e.gz"
OUTPUT_JSON = DATA_DIR / "jmdict_parsed.json"

# Community JLPT overlay (bundled in repo)
JLPT_OVERLAY_PATH = DATA_DIR / "jlpt_overlay.json"


def download_jmdict(force: bool = False) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_GZ.exists() and not force:
        print(f"[JMdict] Using cached file: {CACHE_GZ}")
        return CACHE_GZ
    print(f"[JMdict] Downloading from {JMDICT_URL} …")
    urllib.request.urlretrieve(JMDICT_URL, CACHE_GZ)
    print(f"[JMdict] Saved to {CACHE_GZ} ({CACHE_GZ.stat().st_size / 1e6:.1f} MB)")
    return CACHE_GZ


def load_jlpt_overlay() -> dict[str, str]:
    """
    Load the JLPT level overlay JSON (bundled in data/jlpt_overlay.json).
    Keys are "word|reading" pairs; values are "N5"–"N1".
    """
    if not JLPT_OVERLAY_PATH.exists():
        print(f"[JMdict] JLPT overlay not found at {JLPT_OVERLAY_PATH}. Skipping JLPT tags.")
        return {}
    with open(JLPT_OVERLAY_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    # Normalise to "word|reading" → level
    overlay: dict[str, str] = {}
    for entry in raw:
        word = entry.get("word", "")
        reading = entry.get("reading", word)
        level = entry.get("jlpt", "")
        if word and level:
            overlay[f"{word}|{reading}"] = level
    print(f"[JMdict] Loaded {len(overlay)} JLPT overlay entries.")
    return overlay


def parse_jmdict(gz_path: Path, overlay: dict[str, str]) -> list[dict[str, Any]]:
    print("[JMdict] Parsing XML (this may take ~30 seconds)…")
    entries: list[dict[str, Any]] = []

    with gzip.open(gz_path, "rb") as f:
        tree = etree.parse(f)

    for entry in tree.findall("entry"):
        # Word form (kanji element or reading if no kanji)
        kanji_elems = entry.findall("k_ele/keb")
        reading_elems = entry.findall("r_ele/reb")

        if not reading_elems:
            continue

        word = kanji_elems[0].text if kanji_elems else reading_elems[0].text
        reading = reading_elems[0].text

        # Senses — first English gloss only to keep DB small
        senses = entry.findall("sense")
        if not senses:
            continue

        glosses = senses[0].findall("gloss")
        meaning = "; ".join(g.text for g in glosses if g.text and g.get("{http://www.w3.org/XML/1998/namespace}lang", "eng") == "eng")
        if not meaning:
            meaning = "; ".join(g.text for g in glosses if g.text)
        if not meaning:
            continue

        # Part of speech
        pos_elems = senses[0].findall("pos")
        part_of_speech = _clean_pos(pos_elems[0].text if pos_elems else "")

        # JLPT level — from overlay or inline tag
        level = overlay.get(f"{word}|{reading}", "")
        if not level:
            # Some older JMdict versions embed JLPT tags inline
            misc_elems = entry.findall("sense/misc")
            for misc in misc_elems:
                if misc.text and misc.text.startswith("jlpt"):
                    level = misc.text.upper().replace("JLPT-", "N")
                    break

        entries.append({
            "word": word,
            "reading": reading,
            "meaning": meaning,
            "part_of_speech": part_of_speech,
            "jlpt_level": level,
            "example_jp": None,
            "example_en": None,
        })

    # Keep only entries with a known JLPT level
    tagged = [e for e in entries if e["jlpt_level"] in ("N5", "N4", "N3", "N2", "N1")]
    print(f"[JMdict] Parsed {len(entries)} total entries; {len(tagged)} with JLPT level.")
    return tagged


def _clean_pos(raw: str) -> str:
    """Convert JMdict &pos; entity strings to clean labels."""
    mapping = {
        "v1": "verb", "v5u": "verb", "v5r": "verb", "v5k": "verb", "v5g": "verb",
        "v5s": "verb", "v5t": "verb", "v5n": "verb", "v5b": "verb", "v5m": "verb",
        "vk": "verb", "vs": "verb", "vs-i": "verb", "vz": "verb",
        "adj-i": "adjective", "adj-na": "adjective", "adj-no": "adjective",
        "n": "noun", "n-adv": "noun", "n-suf": "noun", "n-t": "noun",
        "adv": "adverb", "adv-to": "adverb",
        "prt": "particle", "conj": "conjunction", "int": "interjection",
        "pn": "pronoun", "num": "number", "aux-v": "auxiliary verb",
    }
    return mapping.get(raw, raw or "")


def run(force_download: bool = False) -> list[dict[str, Any]]:
    gz = download_jmdict(force=force_download)
    overlay = load_jlpt_overlay()
    entries = parse_jmdict(gz, overlay)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    print(f"[JMdict] Wrote {len(entries)} entries → {OUTPUT_JSON}")
    return entries


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="Re-download even if cached")
    args = p.parse_args()
    run(force_download=args.force)
