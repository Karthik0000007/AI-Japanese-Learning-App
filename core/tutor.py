"""
core/tutor.py — LLaMA3.1 70B tutor via Ollama HTTP streaming API.

Streams text tokens as an async generator.  FastAPI wraps this in a
StreamingResponse with Content-Type: text/event-stream.

Design constraints enforced by the system prompt:
  • NEVER translate Japanese on demand.
  • Always include furigana using <ruby><rb>…</rb><rt>…</rt></ruby> HTML.
  • Explain grammar in English; use Japanese for all examples.
  • Adjust vocabulary in examples to the learner's JLPT level.
"""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum

import httpx

from config import settings
from core.language_detect import detect_language


class TutorMode(str, Enum):
    TEACH = "TEACH"
    QUIZ = "QUIZ"
    EXPLAIN = "EXPLAIN"
    CORRECT = "CORRECT"
    CHAT = "CHAT"


@dataclass
class TutorContext:
    jlpt_level: str = "N5"
    recent_words: list[str] = field(default_factory=list)   # last 10 reviewed
    weak_cards: list[str] = field(default_factory=list)     # lowest ease_factor


# ─── System prompt construction ───────────────────────────────────────────────

_PERSONA_BLOCK = """\
You are Sensei, an expert offline Japanese language tutor helping a student learn Japanese in JLPT N5→N1 order.

RULES (must never be broken):
1. You are a TUTOR, not a translator. Never provide direct Japanese→English translations just because the user asks for one.
   If the user asks "what does X mean?", redirect them to figure it out from context, examples, or related words you provide.
2. Always wrap kanji in furigana using HTML ruby tags: <ruby><rb>食</rb><rt>た</rt></ruby>べる
3. Explain grammar and concepts in English. Use Japanese for all examples, dialogues, and quiz questions.
4. Keep your examples and vocabulary at the learner's specified JLPT level.
5. Be encouraging, precise, and concise. Do not ramble.
"""

_MODE_BLOCKS: dict[TutorMode, str] = {
    TutorMode.TEACH: """\
Mode: TEACH
Introduce ONE grammar point or vocabulary category appropriate for {level}.
Format:
1. Brief English explanation (2–4 sentences)
2. Pattern: [structure in Japanese]
3. Three example sentences using vocabulary the learner already knows
4. One common mistake to avoid
""",
    TutorMode.QUIZ: """\
Mode: QUIZ
Generate ONE fill-in-the-blank or multiple-choice question using words from the learner's recently studied list.
If no recent words are available, choose appropriate N5 vocabulary.
Format:
• Question sentence with ____ for the blank (full Japanese sentence with furigana)
• Four options labeled A/B/C/D (one correct, three plausible distractors)
• Wait for the learner's answer before revealing the correct one.
""",
    TutorMode.EXPLAIN: """\
Mode: EXPLAIN
The learner is asking you to explain a specific word, kanji, or grammar point.
Provide:
1. All readings (on-yomi and kun-yomi for kanji; pitch accent info if relevant)
2. Three real-life example sentences with furigana, increasing in complexity
3. One common usage mistake
4. One related word or kanji to compare/contrast
""",
    TutorMode.CORRECT: """\
Mode: CORRECT
The learner has written Japanese text for you to check.
Identify every error (particle choice, verb conjugation, word order, formality register).
For each error:
• Quote the incorrect part
• Explain WHY it is wrong
• Provide the corrected version
Finally, show the fully corrected sentence with furigana.
Do NOT just re-translate the sentence into English.
""",
    TutorMode.CHAT: """\
Mode: CHAT (free conversation)
Respond naturally as a tutor. Keep the conversation in Japanese as much as possible,
offering English explanations only when the learner is clearly stuck.
""",
}


def _build_system_prompt(mode: TutorMode, ctx: TutorContext) -> str:
    lines = [_PERSONA_BLOCK]

    # Context injection
    lines.append(f"Learner's current JLPT focus level: {ctx.jlpt_level}")

    if ctx.recent_words:
        lines.append(
            "Recently studied vocabulary (use these where relevant): "
            + ", ".join(ctx.recent_words)
        )
    if ctx.weak_cards:
        lines.append(
            "Words the learner finds difficult (reinforce these): "
            + ", ".join(ctx.weak_cards)
        )

    # Mode instruction
    mode_block = _MODE_BLOCKS.get(mode, _MODE_BLOCKS[TutorMode.CHAT])
    lines.append(mode_block.format(level=ctx.jlpt_level))

    return "\n\n".join(lines)


# ─── Streaming response generator ─────────────────────────────────────────────

async def stream_response(
    message: str,
    mode: TutorMode,
    context: TutorContext,
) -> AsyncGenerator[dict, None]:
    """
    Yield token objects with language metadata as they arrive from Ollama.

    Each yielded object contains:
    {
        "token": <str>,           # The text token
        "language": "ja" | "en",  # Detected language of the token
        "sentence_complete": bool # True if this token completes a sentence
    }

    Usage in router:
        async def sse_event_gen():
            async for item in stream_response(msg, mode, ctx):
                yield f"data: {json.dumps(item)}\n\n"
            yield "data: [DONE]\n\n"
    """
    system_prompt = _build_system_prompt(mode, context)

    payload = {
        "model": settings.ollama_model,
        "system": system_prompt,
        "prompt": message,
        "stream": True,
    }

    sentence_buffer = ""  # Accumulate tokens into sentences
    sentence_id = 0
    japanese_sentence_end_chars = "。！？\n"
    english_sentence_end_chars = ".!?\n"

    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream(
                "POST",
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    if not raw_line.strip():
                        continue
                    try:
                        chunk = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    token = chunk.get("response", "")
                    if token:
                        sentence_buffer += token

                        # Check if sentence is complete
                        sentence_complete = False
                        if any(
                            c in token for c in (japanese_sentence_end_chars + english_sentence_end_chars)
                        ):
                            sentence_complete = True
                            sentence_id += 1

                        # Detect language of accumulated sentence
                        language = detect_language(sentence_buffer)

                        yield {
                            "token": token,
                            "language": language,
                            "sentence_complete": sentence_complete,
                            "sentence_id": sentence_id,
                        }

                        # Reset buffer after sentence completes
                        if sentence_complete:
                            sentence_buffer = ""

                    if chunk.get("done"):
                        return
        except httpx.ConnectError:
            error_token = "[ERROR: Ollama is not running. Start it with: ollama serve]"
            yield {
                "token": error_token,
                "language": "en",
                "sentence_complete": True,
                "sentence_id": sentence_id,
            }
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                error_token = (
                    f"[ERROR: Model '{settings.ollama_model}' not found. "
                    f"Pull it with: ollama pull {settings.ollama_model}]"
                )
            else:
                error_token = f"[ERROR: Ollama HTTP {exc.response.status_code}]"
            yield {
                "token": error_token,
                "language": "en",
                "sentence_complete": True,
                "sentence_id": sentence_id,
            }



async def check_ollama_health() -> bool:
    """Return True if Ollama is reachable and the configured model is available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            # Accept partial match (e.g. "llama3.1:70b" matches "llama3.1:70b-instruct-q4")
            return any(settings.ollama_model in m for m in models)
    except Exception:
        return False
