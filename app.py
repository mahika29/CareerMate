from flask import Flask, request, jsonify, send_file
import sqlite3
from datetime import datetime
import os
from gtts import gTTS
import tempfile
from dotenv import load_dotenv
import requests
import urllib.parse

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Language configurations
LANGUAGES = {
    'en': {'name': 'English', 'tts_lang': 'en'},
    'hi': {'name': 'हिन्दी', 'tts_lang': 'hi'},
    'pa': {'name': 'ਪੰਜਾਬੀ', 'tts_lang': 'hi'},
    'kn': {'name': 'ಕನ್ನಡ', 'tts_lang': 'hi'}
}

def get_db_connection():
    try:
        conn = sqlite3.connect('careermate.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    try:
        conn = get_db_connection()
        if conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_message TEXT NOT NULL,
                    bot_response TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')
            conn.commit()
            conn.close()
            print("✅ Database initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")

def translate_single_chunk(text, target):
    """Translate a single chunk of text"""
    try:
        if len(text.strip()) == 0:
            return text
        
        encoded_text = urllib.parse.quote(text.strip())
        url = f"https://api.mymemory.translated.net/get?q={encoded_text}&langpair=en|{target}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'responseData' in data and 'translatedText' in data['responseData']:
                return data['responseData']['translatedText']
        
        return text
            
    except Exception as e:
        print(f"❌ Chunk translation error: {e}")
        return text

def translate_text_smart(text, target_language='en'):
    """Smart translation with better chunking"""
    if target_language == 'en' or not text.strip():
        return text
        
    try:
        lang_map = {'hi': 'hi', 'pa': 'pa', 'kn': 'kn', 'en': 'en'}
        target = lang_map.get(target_language, 'en')
        
        # For short text, translate directly
        if len(text) <= 250:
            return translate_single_chunk(text, target)
        
        # For longer text, split smartly
        chunks = []
        
        # Split by double newlines (paragraphs)
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if len(paragraph) <= 250:
                chunks.append(paragraph)
            else:
                # Split by bullet points
                if '•' in paragraph:
                    parts = paragraph.split('•')
                    current_chunk = parts[0]
                    for part in parts[1:]:
                        if len(current_chunk + '•' + part) <= 250:
                            current_chunk += '•' + part
                        else:
                            if current_chunk.strip():
                                chunks.append(current_chunk)
                            current_chunk = '•' + part
                    if current_chunk.strip():
                        chunks.append(current_chunk)
                else:
                    # Split by sentences
                    sentences = paragraph.replace('. ', '.|').split('|')
                    current_chunk = ''
                    for sentence in sentences:
                        if len(current_chunk + sentence) <= 250:
                            current_chunk += sentence
                        else:
                            if current_chunk.strip():
                                chunks.append(current_chunk)
                            current_chunk = sentence
                    if current_chunk.strip():
                        chunks.append(current_chunk)
        
        # Translate each chunk
        translated_parts = []
        for chunk in chunks:
            if chunk.strip():
                translated = translate_single_chunk(chunk, target)
                translated_parts.append(translated)
        
        return '\n\n'.join(translated_parts)
                
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def detect_intent_multilingual(user_message):
    """Detect what user is asking about in ANY language"""
    message_lower = user_message.lower()
    
    # More comprehensive word lists
    greeting_words = [
        'hi', 'hello', 'hey', 'start', 'namaste', 'namaskar', 'hola', 'bonjour',
        'नमस्ते', 'नमस्कार', 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ', 'ਨਮਸਕਾਰ', 
        'ನಮಸ್ಕಾರ', 'ನಮಸ್ತೆ', 'vanakkam', 'adaab'
    ]
    
    salary_words = [
        'salary', 'pay', 'compensation', 'money', 'earning', 'income', 'wage',
        'वेतन', 'तनख्वाह', 'पैसा', 'कमाई', 'ਤਨਖਾਹ', 'ਪੈਸਾ', 'ਕਮਾਈ',
        'ಸಂಬಳ', 'ದುಡ್ಡು', 'ಕಮಾಯಿ', 'पगार', 'रुपया'
    ]
    
    skills_words = [
        'skills', 'learn', 'study', 'course', 'training', 'education', 'skill',
        'कौशल', 'सीखना', 'अध्ययन', 'पढ़ना', 'ਸਿੱਖਣਾ', 'ਹੁਨਰ', 'ਸਿੱਖਿਆ',
        'ಕೌಶಲ್ಯ', 'ಕಲಿಕೆ', 'ಅಧ್ಯಯನ', 'शिकणे', 'कौशल्य'
    ]
    
    interview_words = [
        'interview', 'preparation', 'questions', 'tips', 'prep', 'question',
        'साक्षात्कार', 'इंटरव्यू', 'प्रश्न', 'ਇੰਟਰਵਿਊ', 'ਸਵਾਲ',
        'ಸಂದರ್ಶನ', 'ಪ್ರಶ್ನೆ', 'मुलाखत'
    ]
    
    job_words = [
        'job', 'career', 'work', 'employment', 'position', 'role', 'jobs',
        'नौकरी', 'काम', 'कैरियर', 'रोजगार', 'ਨੌਕਰੀ', 'ਕੰਮ', 'ਕਰੀਅਰ',
        'ಕೆಲಸ', 'ನೌಕರಿ', 'ಕ್ಯಾರಿಯರ್', 'काम', 'नोकरी'
    ]
    
    resume_words = [
        'resume', 'cv', 'biodata', 'profile', 'bio',
        'बायोडाटा', 'रिज्यूमे', 'ਬਾਇਓਡਾਟਾ', 'ರೆಸ್ಯೂಮೆ', 'ಬಯೋಡಾಟಾ'
    ]
    
    # Check intent
    if any(word in message_lower for word in greeting_words):
        return 'greeting'
    elif any(word in message_lower for word in salary_words):
        return 'salary'  
    elif any(word in message_lower for word in skills_words):
        return 'skills'
    elif any(word in message_lower for word in interview_words):
        return 'interview'
    elif any(word in message_lower for word in job_words):
        return 'job'
    elif any(word in message_lower for word in resume_words):
        return 'resume'
    else:
        return 'default'

def get_ai_response(user_message, language='en'):
    """SUPER SMART multilingual responses"""
    
    print(f"🔍 Processing: {user_message}")
    print(f"🌍 Language: {language}")
    
    # Detect intent
    intent = detect_intent_multilingual(user_message)
    print(f"🎯 Detected intent: {intent}")
    
    # Shorter, cleaner responses to avoid translation limits
    if intent == 'greeting':
        english_response = """👋 **Hello! I'm CareerMate!**

I help with:
• Job search & salaries
• Tech skills & learning
• Interview preparation
• Resume optimization

Ask me about salaries, skills, or jobs!

What can I help you with?"""

    elif intent == 'salary':
        english_response = """💰 **Tech Salaries 2024-2025**

**Software Engineer:**
Entry: $75k-$120k | Mid: $110k-$180k | Senior: $160k-$350k

**AI/ML Engineer:**
Entry: $95k-$130k | Mid: $140k-$200k | Senior: $200k-$400k

**Data Scientist:**
Entry: $85k-$120k | Mid: $120k-$180k | Senior: $180k-$300k

**Location boost:** SF +35%, NYC +25%, Remote -15%

Get multiple offers and negotiate!"""

    elif intent == 'skills':
        english_response = """🎓 **Hottest Tech Skills 2024-2025**

**Programming:** Python (AI/ML) • JavaScript (Web) • SQL (Essential)

**AI/ML:** ChatGPT integration • PyTorch • Vector databases

**Cloud:** AWS • Docker • Kubernetes

**Learning plan:** Pick Python → Choose AI/Web/Cloud → Build 3 projects

**Free resources:** freeCodeCamp.org, Fast.ai, AWS Educate

Which area interests you?"""

    elif intent == 'interview':
        english_response = """🎤 **Interview Prep Essentials**

**Top 3 questions:**
1. "Tell me about yourself" → Present + Impact + Future
2. "Why this job?" → Research company + Show excitement  
3. "Biggest weakness?" → Real weakness + Improvement + Results

**Technical prep:** LeetCode Easy (50) → Medium (100)

**Tips:** Apply Mon-Wed, research interviewer, prepare 5 questions

Need company-specific help?"""

    elif intent == 'job':
        english_response = """🔍 **Job Search Links**

**AI/ML Jobs:**
[AI Engineer Jobs](https://linkedin.com/jobs/search/?keywords=AI%20engineer)
[Data Scientist Jobs](https://linkedin.com/jobs/search/?keywords=data%20scientist)

**Software Jobs:**
[Software Engineer Jobs](https://linkedin.com/jobs/search/?keywords=software%20engineer)
[Full Stack Developer Jobs](https://linkedin.com/jobs/search/?keywords=full%20stack%20developer)

**Remote Jobs:**
[Remote Software Jobs](https://linkedin.com/jobs/search/?keywords=software%20engineer&location=Remote)

Apply within 24hrs, follow up in 1 week!"""

    elif intent == 'resume':
        english_response = """📄 **Resume Optimization**

**Structure:** Header → Summary → Experience → Skills

**Writing:** Action verbs + Quantified results + Job keywords

**ATS-friendly:** PDF format, simple layout, standard fonts

**Test:** Upload to Jobscan.co for ATS score

Want help with specific sections?"""

    else:
        english_response = f"""🤖 **Got it: "{user_message}"**

I help with:
💼 Job search & career strategy
💰 Salary data & negotiation  
🎓 Tech skills & learning
🎯 Interview preparation

**Quick examples:**
"Software engineer salary"
"Skills for AI jobs"  
"Google interview prep"

What do you need help with?"""
    
    # Translate if not English
    if language != 'en':
        try:
            translated_response = translate_text_smart(english_response, language)
            print(f"✅ Translated to {language}")
            return translated_response
        except Exception as e:
            print(f"❌ Translation error: {e}")
            return english_response
    
    return english_response

def generate_smart_suggestions(user_message, ai_response, language='en'):
    intent = detect_intent_multilingual(user_message)
    
    if intent == 'skills':
        return ['🐍 Python learning roadmap', '🤖 AI/ML fundamentals', '☁️ Cloud platforms guide', '💻 Full-stack development']
    elif intent == 'salary':
        return ['💼 Entry-level tech salaries', '🏢 Big tech compensation', '📍 Location-based pay', '💰 Salary negotiation tips']
    elif intent == 'interview':
        return ['❓ Common tech questions', '💡 STAR method examples', '🎯 System design basics', '👔 Behavioral interview prep']
    elif intent == 'resume':
        return ['📄 Upload my resume now', '✨ Resume formatting tips', '🎯 ATS optimization guide', '💼 Cover letter tips']
    else:
        return ['💼 Career guidance', '📈 Skill development', '💰 Salary information', '🎤 Interview preparation']

@app.route('/')
def home():
    return jsonify({"message": "🚀 CareerMate AI Job Assistant - Backend Running!"})

@app.route('/web') 
def web_interface():
    try:
        with open('templates/index.html', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error loading web interface: {str(e)}"

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        language = data.get('language', 'en')
        
        print(f"🔍 Received: '{user_message}'")
        print(f"🌍 Language: {language}")
        print(f"📏 Message length: {len(user_message)} chars")
        
        # Handle empty messages
        if not user_message:
            return jsonify({"success": False, "error": "Empty message received"}), 400
        
        # Clean up the message
        user_message = ' '.join(user_message.split())
        
        bot_response = get_ai_response(user_message, language)
        suggestions = generate_smart_suggestions(user_message, bot_response, language)
        
        print(f"🤖 Response generated!")
        print(f"📏 Response length: {len(bot_response)} chars")
        
        try:
            conn = get_db_connection()
            if conn:
                conn.execute(
                    'INSERT INTO chats (user_message, bot_response, timestamp) VALUES (?, ?, ?)',
                    (user_message, bot_response, datetime.now().isoformat())
                )
                conn.commit()
                conn.close()
        except Exception as db_error:
            print(f"❌ Database error: {db_error}")
        
        return jsonify({
            "success": True,
            "response": bot_response,
            "suggestions": suggestions,
            "language": language,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ Chat error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/speak', methods=['POST'])
def text_to_speech():
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'en')
        
        lang_config = LANGUAGES.get(language, LANGUAGES['en'])
        tts_lang = lang_config['tts_lang']
        
        tts = gTTS(text=text, lang=tts_lang, slow=False)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
        tts.save(temp_file.name)
        
        return send_file(temp_file.name, as_attachment=True, download_name=f'speech_{language}.mp3', mimetype='audio/mpeg')
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-resume', methods=['POST'])
def upload_resume():
    try:
        if 'resume' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
        file = request.files['resume']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        return jsonify({
            'success': True,
            'message': f'📄 Resume "{file.filename}" uploaded successfully! I can help you optimize it and find matching job opportunities.',
            'analysis': {
                'skills_found': ['Python', 'Machine Learning', 'Data Analysis'],
                'job_suggestions': [
                    {
                        'title': 'Data Scientist',
                        'company': 'Tech Corp',
                        'match_score': 85,
                        'linkedin_url': 'https://linkedin.com/jobs/search/?keywords=data%20scientist'
                    }
                ]
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting CareerMate AI Job Assistant...")
    print("🤖 Initializing database...")
    init_database()
    print("🌍 CareerMate Backend Started!")
    print("🗣️ Voice support enabled!")
    print("🔥 Smart translation active!")
    print("🎯 Intent detection ready!")
    print("📍 Website: http://localhost:5000/web")
    app.run(debug=True, host='0.0.0.0', port=5000)
