from flask import Flask, request, jsonify
from transformers import MBartForConditionalGeneration, MBart50Tokenizer
import torch
from flask_cors import CORS
from flask import render_template

app = Flask(__name__)
CORS(app)

# Load model & tokenizer
model_name = "facebook/mbart-large-50-many-to-many-mmt"
tokenizer = MBart50Tokenizer.from_pretrained(model_name)
model = MBartForConditionalGeneration.from_pretrained(model_name)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/translate', methods=['POST'])
def translate():
    data = request.json
    phrase = data.get('phrase', '').strip()

    if not phrase:
        return jsonify({'error': 'No phrase provided'}), 400

    tokenizer.src_lang = "en_XX"
    encoded = tokenizer(phrase, return_tensors="pt").to(device)
    forced_bos_token_id = tokenizer.lang_code_to_id["ja_XX"]

    generated_tokens = model.generate(**encoded, forced_bos_token_id=forced_bos_token_id)
    translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

    # For now, we return only translation
    return jsonify({
        'translation': translated_text,
        'meaning': '',  # You can extend this later
        'example': {'jp': '', 'en': ''}
    })

if __name__ == '__main__':
    app.run(port=5000)

# from flask import Flask, request, jsonify, render_template
# from flask_cors import CORS
# from transformers import MBartForConditionalGeneration, MBart50Tokenizer
# import torch
# import re

# app = Flask(__name__)
# CORS(app)

# # Load model and tokenizer
# model_name = "facebook/mbart-large-50-many-to-many-mmt"
# tokenizer = MBart50Tokenizer.from_pretrained(model_name)
# model = MBartForConditionalGeneration.from_pretrained(model_name)

# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# model.to(device)


# @app.route('/')
# def home():
#     return render_template('index.html')


# @app.route('/translate', methods=['POST'])
# def translate():
#     data = request.json
#     phrase = data.get('phrase', '').strip()

#     if not phrase:
#         return jsonify({'error': 'No phrase provided'}), 400

#     # Very basic language direction inference (can be replaced with ML later)
#     phrase_lower = phrase.lower()

#     # Detect intent from English questions
#     if re.search(r'\b(how do you say|translate|in japanese)\b', phrase_lower):
#         direction = 'en_to_ja'
#         query_match = re.search(r'(?:say|translate)\s+(.+?)\s+(?:in japanese|in japanese\?)?', phrase_lower)
#         if query_match:
#             phrase = query_match.group(1)
#     elif re.search(r'\bwhat does\b', phrase_lower) or re.search(r'\bmean\b', phrase_lower):
#         direction = 'ja_to_en'
#     else:
#         # Detect language from characters
#         if re.search(r'[\u3040-\u30ff\u4e00-\u9faf]', phrase):  # contains Japanese script
#             direction = 'ja_to_en'
#         else:
#             direction = 'en_to_ja'

#     # Set source and target languages
#     if direction == 'en_to_ja':
#         tokenizer.src_lang = "en_XX"
#         target_lang_code = "ja_XX"
#     else:
#         tokenizer.src_lang = "ja_XX"
#         target_lang_code = "en_XX"

#     # Encode and translate
#     encoded = tokenizer(phrase, return_tensors="pt").to(device)
#     forced_bos_token_id = tokenizer.lang_code_to_id[target_lang_code]
#     generated_tokens = model.generate(**encoded, forced_bos_token_id=forced_bos_token_id)
#     translated_text = tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

#     return jsonify({
#         'translation': translated_text,
#         'direction': direction
#     })


# if __name__ == '__main__':
#     app.run(port=5000)
