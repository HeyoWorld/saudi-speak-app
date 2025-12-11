import streamlit as st
import requests
import azure.cognitiveservices.speech as speechsdk
import json
import pandas as pd
import tempfile
import time
import datetime
import os
import uuid

# --- 1. Page Configuration (PWA Ready) ---
st.set_page_config(
    page_title="Saudi Speak | Your AI Language Coach",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# --- 2. Enhanced CSS (App-like UI) ---
st.markdown("""
<style>
    /* Global Font & Colors */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Amiri:wght@400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Arabic Text Styling */
    .rtl { 
        direction: rtl; 
        text-align: right; 
        font-family: 'Amiri', serif; 
        font-size: 1.6rem; 
        line-height: 1.8; 
        color: #1e293b;
    }
    
    .arabic-word {
        font-family: 'Amiri', serif;
        font-size: 1.2rem;
        color: #059669; /* Emerald Green */
        font-weight: bold;
    }

    /* Card Design for Sentences */
    .sentence-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
        border-left: 6px solid #059669;
    }

    /* Feedback Box */
    .feedback-box {
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        color: #166534;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 24px;
        font-size: 0.95rem;
    }
    
    /* Stats/Tracking Info */
    .user-badge {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: -10px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. User Tracking System (Simple CSV Logger) ---
LOG_FILE = "user_activity_log.csv"

def log_user_activity(user_id, user_name, action, content_preview):
    """Logs user actions to a local CSV file for tracking."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_record = {
        "timestamp": timestamp,
        "user_id": user_id,
        "user_name": user_name,
        "action": action,
        "content_preview": content_preview[:50] + "..." if len(content_preview) > 50 else content_preview
    }
    
    # Append to CSV
    df = pd.DataFrame([new_record])
    if not os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, index=False)
    else:
        df.to_csv(LOG_FILE, mode='a', header=False, index=False)

# --- 4. Sidebar: User Profile & Settings ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Flag_of_Saudi_Arabia.svg/320px-Flag_of_Saudi_Arabia.svg.png", width=60)
    st.title("Saudi Speak")
    st.caption("AI-Powered Business Arabic Coach")
    
    st.divider()
    
    # User Identification (For Tracking)
    st.subheader("👤 User Profile")
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = str(uuid.uuid4())[:8] # Generate a session ID
    
    user_name = st.text_input("Your Name", value="Guest", help="Enter your name to track your progress")
    st.caption(f"Session ID: `{st.session_state['user_id']}`")
    
    st.divider()

    # Learning Settings
    st.subheader("⚙️ Settings")
    
    # Style Selector
    learning_mode = st.radio(
        "Target Style",
        ["🗣️ Saudi Dialect (White)", "📜 Formal Arabic (MSA)"],
        captions=["Business casual, networking, daily life", "Contracts, formal speeches, emails"]
    )
    
    # Audio Settings
    speech_rate = st.slider("Speaking Rate", -50, 50, -10, format="%d%%")
    voice_gender = st.selectbox("Voice Coach", ["👨🏻 Hamed (Male)", "🧕🏻 Zariyah (Female)"])
    voice_name = "ar-SA-HamedNeural" if "Hamed" in voice_gender else "ar-SA-ZariyahNeural"

    # API Keys (Hidden in Expander for cleanliness)
    with st.expander("🔑 API Keys (Required)", expanded=True):
        ai_api_key = st.text_input("OpenRouter Key", type="password")
        azure_speech_key = st.text_input("Azure Speech Key", type="password")
        azure_region = st.text_input("Azure Region", value="eastus")

# --- 5. Core Functions ---

def generate_audio_azure(text, key, region, voice, rate):
    if not text or not key: return None
    try:
        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        speech_config.speech_synthesis_voice_name = voice
        rate_str = f"{rate:+d}%"
        ssml = f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="ar-SA">
            <voice name="{voice}">
                <prosody rate="{rate_str}">{text}</prosody>
            </voice>
        </speak>
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        file_config = speechsdk.audio.AudioOutputConfig(filename=temp_file.name)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=file_config)
        result = synthesizer.speak_ssml_async(ssml).get()
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return temp_file.name
        return None
    except: return None

def analyze_text(text, api_key, style):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://saudi-speak-app.com", 
        "X-Title": "Saudi Speak App",
        "Content-Type": "application/json"
    }
    
    style_instruction = (
        "Convert this to natural, educated Saudi White Dialect suitable for business networking."
        if "Saudi" in style else 
        "Convert this to strict Modern Standard Arabic (MSA) suitable for formal documents."
    )

    prompt = f"""
    You are an expert Arabic language coach.
    
    User Input: "{text}"
    Target Style: {style_instruction}
    
    Task:
    1. Polishing: Improve the phrasing to sound native and professional.
    2. Vocalization: Add full Tashkeel (diacritics).
    3. Breakdown: Analyze words and ROOTS.
    
    Return JSON only:
    {{
        "final_text_vocalized": "Full Arabic text with vowels",
        "feedback_note": "English explanation of why you changed the phrasing (if applicable).",
        "sentences": [
            {{
                "segment": "Sentence segment (vocalized)",
                "translation": "English translation",
                "words": [ {{"word": "Arabic Word", "meaning": "English Meaning", "root": "Root (e.g. k-t-b)"}} ]
            }}
        ]
    }}
    """
    
    payload = {
        "model": "google/gemini-2.0-flash-exp:free",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" }
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        return json.loads(response.json()['choices'][0]['message']['content'])
    except Exception as e:
        return {"error": str(e)}

# --- 6. Main Interface ---

st.title("Drill & Master")
st.markdown("<div class='user-badge'>👋 Welcome back, <strong>" + user_name + "</strong></div>", unsafe_allow_html=True)

# Input Area
user_text = st.text_area(
    "What do you want to say?", 
    height=100, 
    placeholder="e.g. Hi, I am the Finance BP for our supply chain division. It's a pleasure to meet you."
)

# Action Button
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("✨ Analyze", type="primary", use_container_width=True):
        if not ai_api_key or not azure_speech_key:
            st.error("⚠️ Please configure API Keys in the sidebar.")
        elif not user_text:
            st.warning("⚠️ Please enter some text.")
        else:
            # TRACKING: Log the request
            log_user_activity(st.session_state['user_id'], user_name, "Analyze", user_text)
            
            with st.spinner("Decoding language patterns..."):
                data = analyze_text(user_text, ai_api_key, learning_mode)
                if "error" not in data:
                    st.session_state['result'] = data
                else:
                    st.error(f"Error: {data['error']}")

# Results Area
# --- Replace EVERYTHING from "# Results Area" downwards with this: ---

# Results Area
if 'result' in st.session_state:
    data = st.session_state['result']
    
    st.divider()
    
    # 1. Feedback Section
    if data.get('feedback_note'):
        # 使用变量拆分，避免 f-string 语法错误
        feedback_html = f"""
        <div class="feedback-box">
            <strong>💡 Coach's Note:</strong> {data['feedback_note']}
        </div>
        """
        st.markdown(feedback_html, unsafe_allow_html=True)
    
    # 2. Full Audio Player
    st.markdown("### 🎧 Full Audio Drill")
    full_audio = generate_audio_azure(data['final_text_vocalized'], azure_speech_key, azure_region, voice_name, speech_rate)
    if full_audio: st.audio(full_audio, format='audio/wav')
    
    st.divider()
    
    # 3. Sentence Breakdown (Cards)
    st.markdown("### 🔁 Shadowing Practice")
    
    for idx, sent in enumerate(data.get('sentences', [])):
        # Card Container
        with st.container():
            # 这里是容易报错的地方，我把它拆开了
            segment_text = sent.get('segment', '')
            translation_text = sent.get('translation', '')
            
            card_html = f"""
            <div class="sentence-card">
                <div class="rtl">{segment_text}</div>
                <div style="color: #64748b; margin-top: 10px; font-weight: 500;">{translation_text}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Controls for this sentence
            c1, c2 = st.columns([1, 5])
            with c1:
                # Individual Audio
                s_audio = generate_audio_azure(segment_text, azure_speech_key, azure_region, voice_name, speech_rate)
                if s_audio: st.audio(s_audio, format='audio/wav')
            
            # Word Analysis (Collapsible)
            with st.expander(f"🔍 Inspect Words (Sentence {idx+1})"):
                # Table Header
                h1, h2, h3 = st.columns([2, 2, 1])
                h1.markdown("**Word**")
                h2.markdown("**Meaning**")
                h3.markdown("**Root**")
                st.markdown("---")
                
                for w in sent.get('words', []):
                    r1, r2, r3 = st.columns([2, 2, 1])
                    
                    word_text = w.get('word', '')
                    word_meaning = w.get('meaning', '')
                    word_root = w.get('root', '-')
                    
                    # 使用单引号 f-string，避免混淆
                    with r1: st.markdown(f"<span class='arabic-word'>{word_text}</span>", unsafe_allow_html=True)
                    with r2: st.write(word_meaning)
                    with r3: st.code(word_root)