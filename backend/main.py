from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
from transformers import MBartForConditionalGeneration, MBart50Tokenizer
import torch
import re
import gc
import logging
import time
import fugashi
from gtts import gTTS
import jaconv
from io import BytesIO

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load model & tokenizer
model_name = "facebook/mbart-large-50-many-to-many-mmt"
tokenizer = MBart50Tokenizer.from_pretrained(model_name)
model = MBartForConditionalGeneration.from_pretrained(model_name)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Fugashi tagger for furigana
tagger = fugashi.Tagger()

@app.route('/')
def home():
    return render_template('index.html')

def split_into_chunks(text, max_chunk_size=400):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current_chunk = [], ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chunk_size:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            if current_chunk: chunks.append(current_chunk)
            current_chunk = sentence
    if current_chunk: chunks.append(current_chunk)
    return chunks

def get_furigana_ruby(text):
    result = []
    for word in tagger(text):
        surface = word.surface
        try:
            reading = word.feature.kana or surface
        except AttributeError:
            reading = surface
        hiragana_reading = jaconv.kata2hira(reading)

        if surface != hiragana_reading and re.search(r'[\u4E00-\u9FAF]', surface):
            result.append(f"<ruby>{surface}<rt>{hiragana_reading}</rt></ruby>")
        else:
            result.append(surface)
    return "".join(result)

# Smart Politeness Controller
def apply_politeness(text, politeness="polite"):
    text = text.strip()
    is_question = text.endswith('?') or text.endswith('？')
    text = text.rstrip('?？')

    polite_endings = ('です', 'ます', 'でした', 'ました', 'ません')

    # Do not apply politeness to common greetings
    greetings = ['こんにちは', 'おはよう', 'こんばんは', 'ありがとう', 'さようなら', 'もしもし']

    if any(text.startswith(greet) for greet in greetings):
        return text  # Skip politeness processing for greetings

    # Simplified rules
    if politeness == "casual":
        if text.endswith('だです') or text.endswith('です'):
            text = text.replace('だです', '').replace('です', '')
    elif politeness == "polite":
        if not text.endswith(polite_endings):
            if text.endswith('だ'):
                text = text[:-1] + 'です'
            else:
                text += 'です'
    elif politeness == "honorific":
        if not text.endswith('でございます'):
            if text.endswith('だ'):
                text = text[:-1] + 'でございます'
            else:
                text += 'でございます'

    if is_question:
        text += 'か？'
    elif not text.endswith(('。', '！', '？')):
        text += '。'

    return text


@app.route('/translate', methods=['POST'])
def translate():
    start_time = time.time()
    try:
        data = request.json
        phrase = data.get('phrase', '').strip()
        politeness = data.get('politeness', 'polite').strip()

        if not phrase:
            return jsonify({'error': 'No phrase provided'}), 400

        # Language detection (simple)
        if re.search(r'[\u3040-\u30ff\u4e00-\u9faf]', phrase):
            tokenizer.src_lang, target_lang = "ja_XX", "en_XX"
        else:
            tokenizer.src_lang, target_lang = "en_XX", "ja_XX"

        chunks = split_into_chunks(phrase)
        translations = []
        for chunk in chunks:
            encoded = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512).to(device)
            generated_tokens = model.generate(
                **encoded,
                forced_bos_token_id=tokenizer.lang_code_to_id[target_lang],
                max_length=512,
                num_beams=4,
                early_stopping=True
            )
            translated_text = tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
            translations.append(translated_text)
            del encoded, generated_tokens
            torch.cuda.empty_cache(); gc.collect()

        full_translation = ' '.join(translations)
        full_translation = apply_politeness(full_translation, politeness)
        furigana_version = get_furigana_ruby(full_translation)
        return jsonify({
            'translation': full_translation,
            'furigana': furigana_version,
            'processing_time': f"{time.time() - start_time:.2f}s"
        })
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

@app.route('/tts', methods=['POST'])
def tts():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400

    mp3_fp = BytesIO()
    tts = gTTS(text=text, lang='ja')
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

if __name__ == '__main__':
    app.run(port=5000)
