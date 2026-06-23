import streamlit as st
import json
import time
import os

# 1. SECURE AUDIO IMPORTS
try:
    import pyaudio
    from vosk import Model, KaldiRecognizer
    AUDIO_AVAILABLE = True
    AUDIO_ERROR = None
except Exception as e:
    AUDIO_AVAILABLE = False
    AUDIO_ERROR = str(e)
    
st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    
    /* Default empty status box */
    .status-box-empty { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #1E2329; 
        border: 1px solid #3E444B; 
        margin-bottom: 8px; 
        color: #6C757D;
    }
    
    /* Successfully validated box (Success Green) */
    .status-box-filled { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #155724; 
        border: 2px solid #28a745; 
        margin-bottom: 8px; 
        color: #D4EDDA;
        font-weight: bold;
    }
    
    /* AI Recommendation container */
    .recommendation-box {
        padding: 20px;
        border-radius: 15px;
        background-color: #0B2545;
        border: 2px solid #134074;
        color: #EEF4F8;
        margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# Only load Vosk if imports were successful and avoid automatic downloads on startup
model = None
if AUDIO_AVAILABLE:
    @st.cache_resource
    def load_vosk():
        model_path = "vosk-model-en-us-0.22"
        if os.path.exists(model_path):
            return Model(model_path)
        return None
    
    try:
        model = load_vosk()
    except Exception as vosk_err:
        AUDIO_AVAILABLE = False
        AUDIO_ERROR = f"Vosk initialization failed: {str(vosk_err)}"

if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'Trigger': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'Success': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''

stages = {
    1: "Hello! Tell me about your role and what brought you here today?",
    2: "What does your current tech stack look like? (Excel, systems...)",
    3: "What is the biggest operational pain costing you time or money?",
    4: "What does personal success look like for you as a leader?",
    5: "What are your hard constraints? (Budget, timeline...)",
    6: "Analysis complete! Here is your diagnostic."
}

def process_text(text):
    text = text.lower()
    
    if any(w in text for w in ['ceo', 'c e o', 'founder', 'director', 'manager', 'leader', 'head', 'vp', 'vice president', 'executive']): 
        st.session_state.slots['Role'] = 'Executive / Decision Maker'
        
    if any(w in text for w in ['problem', 'pain', 'stuck', 'help', 'issue', 'challenge', 'broken', 'difficult', 'brought']): 
        st.session_state.slots['Trigger'] = 'Active Pain Point'
        
    if any(w in text for w in ['excel', 'egg', 'says', 'sheet', 'spread', 'manual', 'legacy', 'old', 'word', 'paper', 'table', 'tableau']): 
        st.session_state.slots['Tech'] = 'Low Maturity (Excel/Manual)'
        
    if any(w in text for w in ['time', 'hours', 'manual', 'slow', 'delay', 'weeks', 'days', 'wasting']): 
        st.session_state.slots['Pain'] = 'Operational Time Loss'
        
    if any(w in text for w in ['fail', 'waste', 'lose', 'expensive', 'cost', 'money', 'drop', 'risk']): 
        st.session_state.tags['Fear'] = 'Wasted Investment / Financial Risk'
        
    if any(w in text for w in ['scale', 'freedom', 'find', 'peace', 'growth', 'expand', 'efficient', 'automate', 'future', 'success']): 
        st.session_state.slots['Success'] = 'Strategic Growth & Automation'
        
    if any(w in text for w in ['budget', 'thousand', 'limit', 'dollar', 'jets', 'price', 'cost', 'expensive', 'timeline', 'month', 'constraints']): 
        st.session_state.slots['Limits'] = 'Tight Resources / Budget Limits'
        
    if any(w in text for w in ['data', 'roi', 'number', 'percent', 'metrics', 'analytics', 'dashboard', 'proof']): 
        st.session_state.tags['Lens'] = 'Data Driven Preference'

st.title("🎙️ Smart Companion")
st.markdown("### Stage " + str(st.session_state.stage) + " / 5")

if not AUDIO_AVAILABLE:
    st.warning(f"⚠️ The audio module could not start properly (Error: {AUDIO_ERROR}). The interface remains accessible.")

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"**Agent says:** {stages[st.session_state.stage]}")
    
    # 1. OPTION MICRO
    if st.button("🔴 Click to Start Speaking"):
        st.write("Listening for 8 seconds...")
        recognizer = KaldiRecognizer(model, 16000)
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=4000)
        stream.start_stream()
        start_time = time.time()
        while time.time() - start_time < 8:
            data = stream.read(4000, exception_on_overflow=False)
            if recognizer.AcceptWaveform(data):
                res = json.loads(recognizer.Result())
                text = res.get('text', '')
                if text:
                    st.session_state.transcript = text
                    process_text(text)
                    break
        stream.stop_stream()
        stream.close()
        p.terminate()
        st.rerun()
    
    st.markdown("---")
    
    # 2. PLAN DE SECOURS : TEXTE MANUEL FORCÉ
    input_key = f"backup_input_stage_{st.session_state.stage}"
    manual_input = st.text_input("⌨️ Backup: Type here if mic fails", key=input_key)
    
    if st.button("💾 Validate text"):
        if manual_input:
            st.session_state.transcript = manual_input
            process_text(manual_input)
            st.rerun()
        
    if st.session_state.transcript:
        st.success(f"Captured: {st.session_state.transcript}")
        
    st.markdown("---")
    # NAVIGATION ALWAYS VISIBLE
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
                st.session_state.transcript = ""
                st.rerun()
                
    with nav_col2:
        if st.button("➡️ Next Stage"):
            if st.session_state.stage < 5:
                st.session_state.stage += 1
                st.session_state.transcript = ""
                st.rerun()
            else:
                st.session_state.stage = 6
                st.rerun()

with col2:
    st.markdown("### 📊 Backend Insights")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Psychological Profiling")
    lens_class = "status-box-filled" if st.session_state.tags['Lens'] != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{lens_class}'><b>Lens:</b> {st.session_state.tags['Lens']}</div>", unsafe_allow_html=True)
    
    fear_class = "status-box-filled" if st.session_state.tags['Fear'] != "None" else "status-box-empty"
    st.markdown(f"<div class='{fear_class}'><b>Fear:</b> {st.session_state.tags['Fear']}</div>", unsafe_allow_html=True)

if st.session_state.stage == 6:
    st.balloons()
    st.header("📋 Final Strategic Diagnostic")
    
    rec_text = "Based on the client profile, Haly recommends a low-risk, phased implementation. "
    if "Excel" in st.session_state.slots['Tech'] or "Manual" in st.session_state.slots['Tech']:
        rec_text += "Priority #1 is migrating manual workflows to a centralized database. "
    if "Time Loss" in st.session_state.slots['Pain'] or "Operational" in st.session_state.slots['Pain']:
        rec_text += "Deploying an LLM-driven document parser will immediately save hours of administrative tasks. "
    if "Budget" in st.session_state.slots['Limits'] or "Resources" in st.session_state.slots['Limits']:
        rec_text += "Structure the deal around an initial ROI-guaranteed MVP to mitigate financial fears."
    else:
        rec_text += "Propose an enterprise-wide AI transformation roadmap focused on high-scalability."

    st.markdown(f"""
    <div class="recommendation-box">
        <h3>🤖 Haly's Strategic Advisory:</h3>
        <p>{rec_text}</p>
        <hr style="border-color: #134074;">
        <small>💡 <b>Sales Pitch Tip:</b> Talk to this client using a <b>{st.session_state.tags['Lens']}</b> approach and address their underlying fear: <i>"{st.session_state.tags['Fear']}"</i>.</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.subheader("Summary Matrix")
    st.write(f"• **Target Prospect:** {st.session_state.slots['Role']}")
    st.write(f"• **Current Tech Maturity:** {st.session_state.slots['Tech']}")
    st.write(f"• **Core Business Bottleneck:** {st.session_state.slots['Pain']}")
    st.write(f"• **Desired Success Metric:** {st.session_state.slots['Success']}")
