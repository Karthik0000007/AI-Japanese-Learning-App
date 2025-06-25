# 🈺 English ⇄ Japanese Smart Translator
### A Real-Time Speech, Text & Furigana Translation App

---

## 🚀 Overview

This project is a fully functional real-time **English ⇄ Japanese translation tool**, integrating:

- 🔁 English ⇄ Japanese translation (with polite/casual/honorific tone control)
- 💬 Furigana (ruby) annotations for kanji
- 🎙️ Text-to-Speech using gTTS
- 🧠 **Grammar/Kanji/JLPT explanation using LLaMA3 via Ollama**
- 🎤 Speech-to-text using browser APIs

> The project evolved through multiple versions — each iteration improving the features and capabilities.
>  
> You’ll find multiple files showing the step-by-step growth of both the frontend and backend.

---
## 🤖 LLaMA3 + Ollama Integration

This project uses the [Ollama](https://ollama.com) runtime to locally run the [Meta LLaMA3](https://ai.meta.com/llama/) model. The assistant is accessed via an endpoint `/japanese_helper`, which returns:
- Vocabulary breakdown with furigana and meanings
- Grammar explanations
- JLPT levels
- Kanji readings and meanings

---
> 💡 This allows offline, secure, and highly contextual Japanese language tutoring directly from an LLM.

## 📂 Project Structure

```bash
root/
│
├── Frontend/
│   ├── index.html         # Initial basic UI version
│   ├── index2.html         # Added speech input
│   ├── index3.html         # Improved UI design
│   ├── index4.html         # Added TTS functionality
│   ├── index5.html         # Integrated Furigana display
│   ├── main.html           
|   ├── llama.html       # Final complete version. Main file to run
│
├── Backend/
│   ├── app.py           # Initial Flask API with basic translation
│   ├── app2.py           # Added speech-to-text backend
│   ├── app3.py           # Integrated mBART50 model
│   ├── app4.py           # Added Furigana processing using Fugashi
│   ├── app5.py           # Improved error handling and optimizations
│   ├── main.py
|   ├── llama.py      # Added Meta LLaMA3 via Ollama for JLPT grammar assistant. Main file to run
│
├── requirements.txt    # Python dependencies
└── README.md           # (This file)

```

## 🔥 Features
- ✅ Real-time Speech-to-Text (STT) for English input
- ✅ Text input for manual typing
- ✅ Real-time mBART50 powered translation (English ⇄ Japanese)
- ✅ Politeness adjustments for Japanese output
- ✅ Automatic Furigana generation (word-level kana over kanji)
- ✅ Listen to Japanese translation with Text-to-Speech
- ✅ Fully functional responsive frontend

## 🛠️ Technologies Used
- Frontend: HTML5, Vanilla JS, Web Speech API, Fetch API
- Backend: Python, Flask, Flask-CORS
- Machine Learning Model: Facebook mBART50 (via Hugging Face Transformers)
- Japanese NLP: MeCab, Fugashi, jaconv
- Speech Recognition: Browser native (Web Speech API)
- Text-To-Speech: Google gTTS
- Deployment Ready: Fully compatible with cloud platforms

## ⚙️ Setup Instructions
- 1️⃣ Install dependencies
Create a virtual environment (optional but recommended):
python -m venv venv
venv\Scripts\activate     # (Windows)

- Install requirements:
pip install -r requirements.txt

#### Run the LLaMA3 Model
Make sure you have [Ollama installed](https://ollama.com/download):

```bash
ollama run llama3
```

- 2️⃣ Run the Backend
From Backend/ directory:
python llama.py

- 3️⃣ Run the Frontend
Simply open Frontend/llama.html in your browser.

- ✅ Both frontend & backend will communicate via REST API locally.

## 🚀 Future Work 
- Fine-tune mBART model for domain-specific translation.
- Deploy on cloud platforms (Render, HuggingFace, AWS, etc.)
- Add user authentication and history storage.
- Improve furigana rendering using ruby tags for perfect web display.
- Expand language pairs beyond English-Japanese.

## 🧑‍💻 Author
- This project was built as part of my personal language learning + AI research journey.

## 💡 Special Notes
- The multiple versions inside both Frontend and Backend folders represent the evolution of the project, showcasing how features were gradually added and optimized over time.
