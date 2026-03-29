/**
 * static/js/utils/languageDetect.js — Fast language detection using Unicode ranges.
 *
 * Detects Japanese vs English by checking for Unicode character ranges:
 * - Hiragana: U+3040..U+309F
 * - Katakana: U+30A0..U+30FF
 * - Kanji: U+4E00..U+9FFF
 *
 * No external dependencies required.
 */

/**
 * Regex pattern matching hiragana, katakana, or kanji.
 * @type {RegExp}
 */
const JAPANESE_CHAR_PATTERN = /[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/g;

/**
 * Detect language of text (Japanese vs English).
 *
 * Strategy:
 * - If text contains Japanese characters (hiragana/katakana/kanji) → "ja"
 * - Otherwise → "en"
 *
 * @param {string} text - Input text to classify.
 * @returns {string} "ja" or "en"
 */
function detectLanguage(text) {
  if (!text) {
    return "en";  // Default to English for empty text
  }

  // Check if any Japanese character exists
  if (JAPANESE_CHAR_PATTERN.test(text)) {
    return "ja";
  }

  return "en";
}

/**
 * Quick check if text contains any Japanese characters.
 *
 * @param {string} text - Input text.
 * @returns {boolean} True if text contains hiragana, katakana, or kanji.
 */
function hasJapanese(text) {
  if (!text) {
    return false;
  }

  return JAPANESE_CHAR_PATTERN.test(text);
}
