"""
tools/build_sample.py — Build data/sample_n5.json, the small bundled N5 dataset.

The sample lets the app work right after install, without downloading and
parsing the full dictionaries. The generated JSON is committed to the repo;
re-run this script only to change the sample.

Sources (both from the EDRDG, CC BY-SA 4.0, see README "Data attribution"):
  • Kanji: KANJIDIC2 marks 103 kanji with the old JLPT level 4, which is
    today's N5. We keep the 80 most frequent, with real readings and meanings.
  • Vocabulary: JMdict has no JLPT tags, so the *selection* of words is the
    curated list below (commonly taught N5 words). Readings, meanings and
    part of speech are looked up in JMdict, never typed by hand.

Needs data/JMdict_e.gz and data/kanjidic2.xml.gz (downloaded by
tools/fetch_jmdict.py and tools/fetch_kanjidic.py).

Run: python -m tools.build_sample
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

from lxml import etree

DATA_DIR = Path(__file__).parent.parent / "data"
JMDICT_GZ = DATA_DIR / "JMdict_e.gz"
KANJIDIC_GZ = DATA_DIR / "kanjidic2.xml.gz"
OUTPUT_JSON = DATA_DIR / "sample_n5.json"

KANJI_COUNT = 80
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
PRIORITY_TAGS = {"ichi1", "news1", "spec1", "spec2", "gai1"}

# (word, reading). Kana-only words use the same string for both.
N5_WORDS: list[tuple[str, str]] = [
    # People
    ("私", "わたし"), ("人", "ひと"), ("男", "おとこ"), ("女", "おんな"),
    ("子供", "こども"), ("友達", "ともだち"), ("先生", "せんせい"), ("学生", "がくせい"),
    ("父", "ちち"), ("母", "はは"), ("兄", "あに"), ("姉", "あね"),
    ("弟", "おとうと"), ("妹", "いもうと"), ("名前", "なまえ"),
    # Places and things
    ("学校", "がっこう"), ("大学", "だいがく"), ("家", "いえ"), ("部屋", "へや"),
    ("店", "みせ"), ("駅", "えき"), ("病院", "びょういん"), ("銀行", "ぎんこう"),
    ("会社", "かいしゃ"), ("国", "くに"), ("道", "みち"), ("本", "ほん"),
    ("机", "つくえ"), ("椅子", "いす"), ("窓", "まど"), ("門", "もん"),
    ("電話", "でんわ"), ("新聞", "しんぶん"), ("手紙", "てがみ"), ("写真", "しゃしん"),
    ("映画", "えいが"), ("音楽", "おんがく"), ("お金", "おかね"), ("仕事", "しごと"),
    ("電車", "でんしゃ"), ("車", "くるま"), ("自転車", "じてんしゃ"),
    ("テレビ", "テレビ"), ("ドア", "ドア"), ("カメラ", "カメラ"),
    # Food and drink
    ("水", "みず"), ("お茶", "おちゃ"), ("肉", "にく"), ("魚", "さかな"),
    ("野菜", "やさい"), ("果物", "くだもの"), ("ご飯", "ごはん"), ("卵", "たまご"),
    ("パン", "パン"), ("コーヒー", "コーヒー"),
    # Nature and animals
    ("山", "やま"), ("川", "かわ"), ("海", "うみ"), ("空", "そら"),
    ("雨", "あめ"), ("天気", "てんき"), ("花", "はな"), ("犬", "いぬ"),
    ("猫", "ねこ"), ("鳥", "とり"),
    # Body
    ("手", "て"), ("足", "あし"), ("目", "め"), ("耳", "みみ"),
    ("口", "くち"), ("頭", "あたま"), ("体", "からだ"),
    # Language
    ("言葉", "ことば"), ("日本", "にほん"), ("日本語", "にほんご"), ("英語", "えいご"),
    # Directions and positions
    ("東", "ひがし"), ("西", "にし"), ("南", "みなみ"), ("北", "きた"),
    ("右", "みぎ"), ("左", "ひだり"), ("上", "うえ"), ("下", "した"),
    ("中", "なか"), ("外", "そと"), ("前", "まえ"), ("後ろ", "うしろ"),
    # Time
    ("今日", "きょう"), ("明日", "あした"), ("昨日", "きのう"), ("毎日", "まいにち"),
    ("朝", "あさ"), ("昼", "ひる"), ("夜", "よる"), ("今", "いま"),
    ("時間", "じかん"), ("年", "とし"), ("月", "つき"),
    # Numbers and money
    ("一", "いち"), ("二", "に"), ("三", "さん"), ("十", "じゅう"),
    ("百", "ひゃく"), ("千", "せん"), ("万", "まん"), ("円", "えん"),
    # Verbs
    ("食べる", "たべる"), ("飲む", "のむ"), ("行く", "いく"), ("来る", "くる"),
    ("帰る", "かえる"), ("見る", "みる"), ("聞く", "きく"), ("読む", "よむ"),
    ("書く", "かく"), ("話す", "はなす"), ("買う", "かう"), ("会う", "あう"),
    ("待つ", "まつ"), ("起きる", "おきる"), ("寝る", "ねる"), ("休む", "やすむ"),
    ("働く", "はたらく"), ("分かる", "わかる"), ("住む", "すむ"), ("入る", "はいる"),
    ("出る", "でる"), ("歩く", "あるく"), ("泳ぐ", "およぐ"), ("遊ぶ", "あそぶ"),
    ("作る", "つくる"), ("教える", "おしえる"), ("習う", "ならう"), ("開ける", "あける"),
    ("使う", "つかう"), ("立つ", "たつ"), ("言う", "いう"), ("勉強", "べんきょう"),
    # Adjectives
    ("大きい", "おおきい"), ("小さい", "ちいさい"), ("新しい", "あたらしい"), ("古い", "ふるい"),
    ("高い", "たかい"), ("安い", "やすい"), ("長い", "ながい"), ("短い", "みじかい"),
    ("暑い", "あつい"), ("寒い", "さむい"), ("白い", "しろい"), ("黒い", "くろい"),
    ("赤い", "あかい"), ("青い", "あおい"), ("早い", "はやい"), ("多い", "おおい"),
    ("楽しい", "たのしい"), ("難しい", "むずかしい"), ("忙しい", "いそがしい"),
    ("元気", "げんき"), ("静か", "しずか"), ("有名", "ゆうめい"), ("好き", "すき"),
    ("上手", "じょうず"), ("便利", "べんり"),
    # Adverbs
    ("少し", "すこし"), ("とても", "とても"), ("もう", "もう"), ("まだ", "まだ"),
]


def main() -> None:
    missing = [p for p in (JMDICT_GZ, KANJIDIC_GZ) if not p.exists()]
    if missing:
        sys.exit(
            f"Missing {', '.join(str(p) for p in missing)}. Run python tools/fetch_jmdict.py "
            "and python tools/fetch_kanjidic.py first. (The committed data/sample_n5.json "
            "already works; you only need this script to change the sample.)"
        )

    vocab = build_vocab()
    kanji = build_kanji(vocab)

    sample = {
        "source": "JMdict and KANJIDIC2, (c) EDRDG, CC BY-SA 4.0. Built by tools/build_sample.py.",
        "vocab": vocab,
        "kanji": kanji,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sample, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"[sample] Wrote {len(vocab)} vocab and {len(kanji)} kanji -> {OUTPUT_JSON}")


# ─── Vocabulary (JMdict) ──────────────────────────────────────────────────────

def build_vocab() -> list[dict[str, Any]]:
    wanted = set(N5_WORDS)
    candidates: dict[tuple[str, str], list[etree._Element]] = {key: [] for key in wanted}

    with gzip.open(JMDICT_GZ, "rb") as f:
        for _, entry in etree.iterparse(f, tag="entry"):
            kebs = [k.text for k in entry.findall("k_ele/keb")]
            rebs = [r.text for r in entry.findall("r_ele/reb")]
            for word, reading in _keys_for(kebs, rebs):
                if (word, reading) in wanted:
                    candidates[(word, reading)].append(_copy(entry))
            entry.clear()

    not_found = [key for key in N5_WORDS if not candidates[key]]
    if not_found:
        sys.exit(f"Not found in JMdict, fix N5_WORDS: {not_found}")

    rows = []
    for word, reading in N5_WORDS:
        entry = min(candidates[(word, reading)], key=_rank)
        sense = entry.find("sense")
        glosses = [g.text for g in sense.findall("gloss") if g.text and g.get(XML_LANG, "eng") == "eng"]
        pos = sense.find("pos")
        rows.append({
            "word": word,
            "reading": reading,
            "meaning": "; ".join(glosses[:3]),
            "part_of_speech": short_pos(pos.text if pos is not None else ""),
            "jlpt_level": "N5",
            "example_jp": None,
            "example_en": None,
        })
    return rows


def _keys_for(kebs: list[str], rebs: list[str]):
    """All (word, reading) pairs an entry can match: kanji form + reading, or kana alone."""
    for reb in rebs:
        yield reb, reb
        for keb in kebs:
            yield keb, reb


def _copy(entry: etree._Element) -> etree._Element:
    return etree.fromstring(etree.tostring(entry))


def _rank(entry: etree._Element) -> tuple[int, int]:
    """Prefer common entries (priority tags), then the lowest sequence number."""
    tags = {p.text for p in entry.iter("ke_pri", "re_pri")}
    return (0 if tags & PRIORITY_TAGS else 1, int(entry.findtext("ent_seq")))


def short_pos(description: str) -> str:
    """Turn JMdict's long part-of-speech text into the app's short labels."""
    d = description.lower()
    if "adjective" in d or "adjectival" in d:
        return "adjective"
    if "verb" in d and "adverb" not in d:
        return "verb"
    if "adverb" in d:
        return "adverb"
    if "noun" in d:
        return "noun"
    if "numeric" in d:
        return "number"
    if "pronoun" in d:
        return "pronoun"
    return d


# ─── Kanji (KANJIDIC2) ───────────────────────────────────────────────────────

def build_kanji(vocab: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    with gzip.open(KANJIDIC_GZ, "rb") as f:
        for _, char in etree.iterparse(f, tag="character"):
            if char.findtext("misc/jlpt") == "4":  # old JLPT level 4 = N5
                freq = char.findtext("misc/freq")
                rows.append({
                    "character": char.findtext("literal"),
                    "on_yomi": [r.text for r in char.iter("reading") if r.get("r_type") == "ja_on"],
                    "kun_yomi": [r.text for r in char.iter("reading") if r.get("r_type") == "ja_kun"],
                    "meaning": [m.text for m in char.iter("meaning") if m.get("m_lang") is None],
                    "stroke_count": int(char.findtext("misc/stroke_count")),
                    "jlpt_level": "N5",
                    "freq_rank": int(freq) if freq else None,
                    "example_word": None,
                    "example_sentence": None,
                })
            char.clear()

    rows.sort(key=lambda r: (r["freq_rank"] is None, r["freq_rank"] or 0))
    rows = rows[:KANJI_COUNT]

    # Example word: the first sample word that uses this kanji
    for row in rows:
        for v in vocab:
            if row["character"] in v["word"]:
                row["example_word"] = f"{v['word']} ({v['reading']})"
                break
    return rows


if __name__ == "__main__":
    main()
