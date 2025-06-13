🈺 English ⇄ Japanese Smart Translator
A Real-Time Speech, Text & Furigana Translation App

🚀 Overview
This project is a fully functional real-time English ⇄ Japanese translation tool, integrating:
✨ Speech Recognition (STT)
✨ Text Translation using mBART50 (Hugging Face Transformers)
✨ Furigana (ruby readings) extraction using MeCab + Fugashi
✨ Text-to-Speech (TTS) for Japanese output using gTTS
✨ Beautiful Frontend with speech-enabled UI

The project evolved through multiple versions — each iteration improving the features and capabilities.
You’ll find multiple files showing the step-by-step growth of both the frontend and backend.

📂 Project Structure
bash
Copy
Edit
root/
│
├── Frontend/
│   ├── v1.html         # Initial basic UI version
│   ├── v2.html         # Added speech input
│   ├── v3.html         # Improved UI design
│   ├── v4.html         # Added TTS functionality
│   ├── v5.html         # Integrated Furigana display
│   ├── main.html         # Final complete version. Main file to run
│
├── Backend/
│   ├── v1.py           # Initial Flask API with basic translation
│   ├── v2.py           # Added speech-to-text backend
│   ├── v3.py           # Integrated mBART50 model
│   ├── v4.py           # Added Furigana processing using Fugashi
│   ├── v5.py           # Improved error handling and optimizations
│   ├── main.py          # Politeness and natural language improvements. Main file to run
│
├── requirements.txt    # Python dependencies
└── README.md           # (This file)


🔥 Features
✅ Real-time Speech-to-Text (STT) for English input
✅ Text input for manual typing
✅ Real-time mBART50 powered translation (English ⇄ Japanese)
✅ Politeness adjustments for Japanese output
✅ Automatic Furigana generation (word-level kana over kanji)
✅ Listen to Japanese translation with Text-to-Speech
✅ Fully functional responsive frontend

🛠️ Technologies Used
Frontend: HTML5, Vanilla JS, Web Speech API, Fetch API
Backend: Python, Flask, Flask-CORS
Machine Learning Model: Facebook mBART50 (via Hugging Face Transformers)
Japanese NLP: MeCab, Fugashi, jaconv
Speech Recognition: Browser native (Web Speech API)
Text-To-Speech: Google gTTS
Deployment Ready: Fully compatible with cloud platforms

⚙️ Setup Instructions
1️⃣ Install dependencies
Create a virtual environment (optional but recommended):
python -m venv venv
venv\Scripts\activate     # (Windows)

Install requirements:
pip install -r requirements.txt

2️⃣ Run the Backend
From Backend/ directory:
python main.py

3️⃣ Run the Frontend
Simply open Frontend/main.html in your browser.

✅ Both frontend & backend will communicate via REST API locally.

🚀 Future Work 
Fine-tune mBART model for domain-specific translation.
Deploy on cloud platforms (Render, HuggingFace, AWS, etc.)
Add user authentication and history storage.
Improve furigana rendering using ruby tags for perfect web display.
Expand language pairs beyond English-Japanese.

🧑‍💻 Author
This project was built as part of my personal language learning + AI research journey.

💡 Special Notes
The multiple versions inside both Frontend and Backend folders represent the evolution of the project, showcasing how features were gradually added and optimized over time.
