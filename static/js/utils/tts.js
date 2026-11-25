/**
 * static/js/utils/tts.js - Shared helpers for choosing pronounceable TTS text.
 */

function normalizeKanjiReading(reading) {
  return String(reading ?? "")
    .replace(/[.\-]/g, "")
    .trim();
}

function firstReadableKanjiText(kanji) {
  if (!kanji) return "";

  const candidates = [
    kanji.example_word,
    ...(kanji.kun_yomi ?? []),
    ...(kanji.on_yomi ?? []),
    kanji.character,
  ];

  for (const candidate of candidates) {
    const normalized = normalizeKanjiReading(candidate);
    if (normalized) return normalized;
  }

  return "";
}

function getTtsTextForCard(card) {
  if (!card) return "";

  if (card.vocab) return card.vocab.reading ?? card.vocab.word ?? "";
  if (card.kanji) return firstReadableKanjiText(card.kanji);

  if (card.reading) return card.reading;
  if (card.word) return card.word;

  return firstReadableKanjiText(card);
}
