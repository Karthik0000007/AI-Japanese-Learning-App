from flask import Flask, request, jsonify, render_template, abort, send_file
from flask_cors import CORS
from transformers import MBartForConditionalGeneration, MBart50Tokenizer
import torch
import re
import gc
import logging
import time
import whisper
import os
import fugashi
from gtts import gTTS
import jaconv
import subprocess
from io import BytesIO
import ffmpeg
import soundfile as sf
import traceback

# Setup Flask
app = Flask(__name__)
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load MBART model
model_name = "facebook/mbart-large-50-many-to-many-mmt"
tokenizer = MBart50Tokenizer.from_pretrained(model_name)
model = MBartForConditionalGeneration.from_pretrained(
    model_name,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
logger.info(f"Translation model loaded on {device}")

# Whisper model for speech-to-text
whisper_model = whisper.load_model("base")
logger.info("Whisper model loaded")

# Fugashi tagger for furigana
tagger = fugashi.Tagger()

# Routes
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

def get_furigana(text):
    result = []
    for word in tagger(text):
        surface = word.surface
        try:
            reading = word.feature.kana or surface  # Works with UnidicFeatures
        except AttributeError:
            reading = surface
        hiragana_reading = jaconv.kata2hira(reading)
        if surface != hiragana_reading:
            result.append(f"{surface}({hiragana_reading})")
        else:
            result.append(surface)
    return " ".join(result)


@app.route('/translate', methods=['POST'])
def translate():
    start_time = time.time()
    try:
        data = request.get_json()
        phrase = data.get('phrase', '').strip()
        if not phrase:
            return jsonify({'error': 'No phrase provided'}), 400

        # Language direction detection
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
        furigana_version = get_furigana(full_translation)
        return jsonify({
            'translation': full_translation,
            'furigana': furigana_version,
            'processing_time': f"{time.time() - start_time:.2f}s"
        })

    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({'error': 'Server error', 'details': str(e)}), 500

@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    logger.info("speech_to_text called")

    # 1️⃣ Check if audio file is present
    if 'audio' not in request.files:
        logger.error("No audio file in request")
        return jsonify({'error': 'No audio file uploaded'}), 400

    uploaded_file = request.files['audio']

    input_path = os.path.join(os.getcwd(), "temp_audio.webm")
    output_path = os.path.join(os.getcwd(), "converted_audio.wav")

    try:
        # Save input file
        uploaded_file.save(input_path)
        file_size = os.path.getsize(input_path)
        logger.info(f"Received audio file. Size: {file_size} bytes")

        if file_size < 1000:  # Less than 1KB likely empty
            logger.warning("Uploaded file seems empty")
            return jsonify({'error': 'Uploaded file is empty or invalid'}), 400

        # 2️⃣ Convert WebM to WAV (Whisper-friendly)
        logger.info("Starting ffmpeg conversion")
        ffmpeg.input(input_path).output(
            output_path,
            format='wav',
            acodec='pcm_s16le',
            ac=1,
            ar='16000'
        ).global_args('-loglevel', 'error').run(overwrite_output=True)
        logger.info(f"Audio converted to WAV: {output_path}")

        # 3️⃣ Sanity check WAV file
        data, samplerate = sf.read(output_path)
        duration_seconds = data.shape[0] / samplerate
        logger.info(f"Samplerate: {samplerate}, Duration: {duration_seconds:.2f} seconds")

        if duration_seconds < 0.5:
            logger.warning("Audio too short for transcription")
            return jsonify({'error': 'Audio too short or silent'}), 400

        # 4️⃣ Transcribe with Whisper
        logger.info("Starting transcription with Whisper")
        result = whisper_model.transcribe(output_path)
        text = result.get('text', '').strip()
        logger.info(f"Transcription result: {text}")

        if not text:
            text = "(No speech detected)"

        return jsonify({'text': text})

    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': 'Transcription failed', 'details': str(e)}), 500

    finally:
        # Clean up files
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)
# @app.route('/speech_to_text', methods=['POST'])
# def speech_to_text():
#     data = request.json
#     phrase = data.get('phrase', '').strip()

#     if not phrase:
#         return jsonify({'error': 'No phrase provided'}), 400

#     tokenizer.src_lang = "en_XX"
#     encoded = tokenizer(phrase, return_tensors="pt").to(device)
#     forced_bos_token_id = tokenizer.lang_code_to_id["ja_XX"]

#     generated_tokens = model.generate(**encoded, forced_bos_token_id=forced_bos_token_id)
#     translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

#     # For now, we return only translation
#     return jsonify({
#         'translation': translated_text,
#         'meaning': '',  # You can extend this later
#         'example': {'jp': '', 'en': ''}
#     })

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
    app.run(host='0.0.0.0', port=5000, threaded=True) 
