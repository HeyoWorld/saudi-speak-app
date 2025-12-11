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

# --- 1. Page Configuration ---
st.set_page_config(
    page_title="Saudi Speak | AI Coach",
    layout="wide",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# --- 2. Load Secrets (Auto-Login) ---
# 尝试从后台读取 Key，如果读不到，就在界面上报错提示
try:
    AI_API_KEY = st.secrets["AI_API_KEY"]
    AZURE_SPEECH_KEY = st.secrets["AZURE_SPEECH_KEY"]
    AZURE_REGION = st.secrets["AZURE_REGION"]
    SYSTEM_READY = True
except FileNotFoundError:
    st.error("⚠️ 错误：未找到 secrets.toml 文件。请在 .streamlit 文件夹中配置 API Key。")
    SYSTEM_READY = False
except KeyError as e:
    st.error(f"⚠️ 错误：Secrets 中缺少配置项 {e}。请检查配置。")
    SYSTEM_READY = False

# --- 3. Enhanced UI Styling (Google Dark Mode Style) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Amiri:wght@400;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* RTL Arabic Text */
    .rtl { 
        direction: rtl; 
        text-align: right; 
        font-family: 'Amiri', serif; 
        font-size: 1.6rem; 
        line-height: 1.8; 
        color: #e2e8f0; /* Light text for dark mode */
    }
    
    .arabic-word {
        font-family: 'Amiri', serif;
        font-size: 1.2rem;
        color: #34d399; /* Emerald Green */
        font-weight: bold;
    }

    /* Cards */
    .sentence-card {
        background-color: #1e293b; /* Dark slate */
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
        border-left: 5px solid #34d399;
    }

    /* Feedback */
    .feedback-box {
        background-color: #064e3b;
        border: 1px solid #059669;
        color: #ecfdf5;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 24px;
    }
    
    .user-badge { font-size: 0.8rem; color: #94a3b8; margin-top: -10px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 4. User Tracking (Simple CSV) ---
LOG_FILE = "user_activity_log.csv"

def log_user_activity(user_id, user_name, action, content_preview):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_record = {
        "timestamp": timestamp,
        "user_id": user_id,
        "user_name": user_name,
        "action": action,
        "content_preview": content_preview[:50].replace("\n", " ")
    }
    df = pd.DataFrame([new_record])
    if not os.path.exists(LOG_FILE):
        df.to_csv(LOG_FILE, index=False)
    else:
        df.to_csv(LOG_FILE, mode='a', header=False, index=False)

# --- 5. Sidebar ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Flag_of_Saudi_Arabia.svg/320px-Flag_of_Saudi_Arabia.svg.png", width=60)
    st.title("Saudi Speak")
    
    # Status Indicator
    if SYSTEM_READY:
        st.success("🟢 System Online")
    else:
        st.error("🔴 Config Missing")

    st.divider()
    
    # User Profile
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = str(uuid.uuid4())[:8]
    
    user_name = st.text_input("Your Name", value="Guest")
    
    st.divider()

    # Settings
    st.subheader("⚙️ Settings")
    learning_mode = st.radio(
        "Style",
        ["🗣️ Saudi Dialect (Business)", "📜 Formal Arabic (MSA)"],
    )
    
    speech_rate = st.slider("Speed", -50, 50, -10, format="%d%%")
    voice_gender = st.selectbox("Voice", ["👨🏻 Hamed (Male)", "🧕🏻 Zariyah (Female)"])
    voice_name = "ar-SA-HamedNeural" if "Hamed" in voice_gender else "ar-SA-ZariyahNeural"

# --- 6. Core Functions ---

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
    1. Polishing: Improve the phrasing to sound native.
    2. Vocalization: Add full Tashkeel.
    3. Breakdown: Analyze words and ROOTS.
    
    Return JSON only:
    {{
        "final_text_vocalized": "Full Arabic text with vowels",
        "feedback_note": "English explanation of changes.",
        "sentences": [
            {{
                "segment": "Sentence segment",
                "translation": "English translation",
                "words": [ {{"word": "Arabic Word", "meaning": "Meaning", "root": "Root"}} ]
            }}
        ]
    }}
    """
    
    # 使用比较稳的 Gemini Flash 1.5
    payload = {
        "model": "google/gemini-2.0-flash-lite-001", 
        "messages": [{"role": "user", "content": prompt}],
        "response_format": { "type": "json_object" }
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60)
        
        # Error Handling Logic
        if response.status_code != 200:
            return {"error": f"API Error {response.status_code}: {response.text}"}
            
        result = response.json()
        if 'choices' not in result:
            return {"error": f"Model Error: {result}"}
            
        content = result['choices'][0]['message']['content']
        clean_content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_content)

    except Exception as e:
        return {"error": str(e)}

# --- 7. Main Interface ---

st.title("Drill & Master")
st.markdown(f"<div class='user-badge'>👋 Welcome, <strong>{user_name}</strong></div>", unsafe_allow_html=True)

user_text = st.text_area(
    "What do you want to practice?", 
    height=100, 
    placeholder="e.g. I need to introduce myself to the new VP of Marketing."
)

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("✨ Analyze", type="primary", use_container_width=True, disabled=not SYSTEM_READY):
        if not user_text:
            st.warning("Please enter some text.")
        elif SYSTEM_READY:
            log_user_activity(st.session_state['user_id'], user_name, "Analyze", user_text)
            
            with st.spinner("Consulting AI Coach..."):
                data = analyze_text(user_text, AI_API_KEY, learning_mode)
                if "error" not in data:
                    st.session_state['result'] = data
                else:
                    st.error(data['error'])

# Results Display
if 'result' in st.session_state:
    data = st.session_state['result']
    
    st.divider()
    
    # Feedback
    if data.get('feedback_note'):
        feedback_html = f"""
        <div class="feedback-box">
            <strong>💡 Coach's Note:</strong> {data['feedback_note']}
        </div>
        """
        st.markdown(feedback_html, unsafe_allow_html=True)
    
    # Full Audio
    st.markdown("### 🎧 Full Audio")
    full_audio = generate_audio_azure(data['final_text_vocalized'], AZURE_SPEECH_KEY, AZURE_REGION, voice_name, speech_rate)
    if full_audio: st.audio(full_audio, format='audio/wav')
    
    st.divider()
    
    # Shadowing Cards
    st.markdown("### 🔁 Shadowing")
    
    for idx, sent in enumerate(data.get('sentences', [])):
        with st.container():
            seg = sent.get('segment', '')
            trans = sent.get('translation', '')
            
            card_html = f"""
            <div class="sentence-card">
                <div class="rtl">{seg}</div>
                <div style="color: #cbd5e1; margin-top: 10px; font-size: 0.9em;">{trans}</div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            # Audio Control
            c1, c2 = st.columns([1, 4])
            with c1:
                s_audio = generate_audio_azure(seg, AZURE_SPEECH_KEY, AZURE_REGION, voice_name, speech_rate)
                if s_audio: st.audio(s_audio, format='audio/wav')
            
            # Words Expander
            with st.expander(f"🔍 Words Analysis"):
                h1, h2, h3 = st.columns([2, 2, 1])
                h1.markdown("**Word**")
                h2.markdown("**Meaning**")
                h3.markdown("**Root**")
                st.markdown("---")
                
                for w in sent.get('words', []):
                    r1, r2, r3 = st.columns([2, 2, 1])
                    with r1: st.markdown(f"<span class='arabic-word'>{w.get('word','')}</span>", unsafe_allow_html=True)
                    with r2: st.write(w.get('meaning',''))
                    with r3: st.code(w.get('root','-'))