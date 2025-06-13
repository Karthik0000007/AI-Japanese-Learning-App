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

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load model and tokenizer with optimizations
model_name = "facebook/mbart-large-50-many-to-many-mmt"
tokenizer = MBart50Tokenizer.from_pretrained(model_name)
try:
    model = MBartForConditionalGeneration.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    )
except:
    model = MBartForConditionalGeneration.from_pretrained(model_name)

# Device configuration
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
logger.info(f"Model loaded on device: {device}")

@app.route('/')
def home():
    return render_template('index.html')

@app.before_request
def log_request_info():
    logger.info(f"Request: {request.method} {request.path}")

def split_into_chunks(text, max_chunk_size=400):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chunk_size:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

tagger = fugashi.Tagger()

def get_furigana(text):
    result = []
    for word in tagger(text):
        surface = word.surface
        reading = word.feature.pron or surface
        hiragana_reading = jaconv.kata2hira(reading)
        if surface != hiragana_reading:
            result.append(f"{surface}({hiragana_reading})")
        else:
            result.append(surface)
    return " ".join(result)

# Add polite post-processor function here:
def apply_politeness(text):
    # Only for Japanese output, add "です" if ending sounds incomplete
    polite_endings = ['は', 'が', 'を', 'に', 'で', 'と', 'から', 'まで', 'より', 'の', 'も']
    if text.endswith(tuple(polite_endings)):
        text += "です"
    elif not text.endswith(('です', 'ます', 'だ', 'よ', 'ね', '！', '？', '。')):
        text += "です"
    return text

# Load whisper once
whisper_model = whisper.load_model("base")

@app.route('/speech_to_text', methods=['POST'])
def speech_to_text():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400
    
    audio = request.files['audio']
    filename = "temp_audio.wav"
    audio.save(filename)
    
    result = whisper_model.transcribe(filename)
    
    os.remove(filename)
    return jsonify({'text': result['text']})

@app.route('/translate', methods=['POST'])
def translate():
    start_time = time.time()
    timeout = 30
    
    try:
        data = request.get_json()
        phrase = data.get('phrase', '').strip()
        
        if not phrase:
            logger.warning("Empty translation request received")
            return jsonify({'error': 'No phrase provided'}), 400
        
        if re.search(r'[\u3040-\u30ff\u4e00-\u9faf]', phrase):
            tokenizer.src_lang = "ja_XX"
            target_lang = "en_XX"
        else:
            tokenizer.src_lang = "en_XX"
            target_lang = "ja_XX"
        
        chunks = split_into_chunks(phrase)
        logger.info(f"Processing {len(chunks)} chunk(s) for translation")
        
        translations = []
        for i, chunk in enumerate(chunks):
            if time.time() - start_time > timeout:
                logger.warning("Translation timeout")
                abort(504, description="Translation timeout")
                
            try:
                encoded = tokenizer(
                    chunk,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512
                ).to(device)
                
                generated_tokens = model.generate(
                    **encoded,
                    forced_bos_token_id=tokenizer.lang_code_to_id[target_lang],
                    max_length=512,
                    num_beams=4,
                    early_stopping=True
                )
                
                translated_text = tokenizer.decode(
                    generated_tokens[0],
                    skip_special_tokens=True
                )
                translations.append(translated_text)
                
                del encoded, generated_tokens
                torch.cuda.empty_cache()
                gc.collect()
                
            except RuntimeError as e:
                if "CUDA out of memory" in str(e):
                    logger.error(f"Memory error on chunk {i}: {str(e)}")
                    return jsonify({
                        'error': 'Text too long - please try shorter segments',
                        'translated_so_far': ' '.join(translations)
                    }), 413
                raise
        
        full_translation = ' '.join(translations)

        # Apply politeness correction only for Japanese output
        if target_lang == "ja_XX":
            full_translation = apply_politeness(full_translation)

        furigana_version = get_furigana(full_translation)
        
        return jsonify({
                'translation': full_translation,
                'furigana': furigana_version,
                'processing_time': f"{time.time() - start_time:.2f}s",
                'chunks_processed': len(chunks)
        })
        
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Server error during translation',
            'details': str(e)
        }), 500

@app.route('/tts', methods=['POST'])
def tts():
    data = request.get_json()
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    tts = gTTS(text=text, lang='ja')
    tts.save("output.mp3")
    return send_file("output.mp3", mimetype="audio/mpeg")

@app.route('/batch_translate', methods=['POST'])
def batch_translate():
    try:
        data = request.get_json()
        texts = data.get('texts', [])
        
        if not texts or not isinstance(texts, list):
            return jsonify({'error': 'No texts array provided'}), 400
            
        results = []
        for text in texts:
            try:
                response = app.test_client().post(
                    '/translate',
                    json={'phrase': text},
                    headers={'Content-Type': 'application/json'}
                )
                result = response.get_json()
                results.append({
                    'original': text,
                    'translation': result.get('translation'),
                    'error': result.get('error')
                })
            except Exception as e:
                results.append({
                    'original': text,
                    'error': str(e)
                })
                
        return jsonify({'results': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)
