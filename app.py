import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# SYSTEM PROMPT COMPLETELY AGNOSTIC TO ANY SPECIFIC SCENARIO
SYSTEM_PROMPT = """
You are a rigorous, literal B2B sales data extractor operating with strict inferential discipline. 
Your sole objective is to parse the latest client transcript turn and populate the target slots and psychological tags based ONLY on explicit facts provided.

[CRITICAL INFERENTIAL DIRECTIVES]
1. ZERO INFERENCE: Do not assume, extrapolate, or invent details. If a parameter is not explicitly detailed or defined by the client's direct text, it MUST remain or be set to 'Empty'.
2. COMPANY SIZE RULE: If the prospect is vague, evasive, or explicitly avoids giving a precise metric or definitive scale (e.g., saying 'not huge, not small, in-between', 'decent-sized'), you are strictly forbidden from guessing 'Medium' or 'Large'. You MUST leave 'CompanySize' as 'Empty'.
3. NO SCENARIO BIAS: Do not inject concepts like 'marketing attribution', 'Zero-Trust', or 'reporting' unless those exact technical words or explicit contexts are typed by the user in the current session.
"""

st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

# CSS Styling
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    .status-box-empty { padding: 12px; border-radius: 10px; background-color: #1E2329; border: 1px solid #3E444B; margin-bottom: 8px; color: #6C757D; }
    .status-box-filled { padding: 12px; border-radius: 10px; background-color: #155724; border: 2px solid #28a745; margin-bottom: 8px; color: #D4EDDA; font-weight: bold; }
    .recommendation-box { padding: 25px; border-radius: 15px; background-color: #0B2545; border: 2px solid #134074; color: #EEF4F8; margin-top: 15px; margin-bottom: 20px; line-height: 1.6; }
    .priority-badge-high { display: inline-block; background-color: #E63946; color: white; padding: 6px 14px; font-size: 0.85em; font-weight: bold; border-radius: 4px; letter-spacing: 1px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

# 2. BULLETPROOF RESET MECHANISM
def execute_hard_reset():
    # Completely clear session state dictionary
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Re-initialize clean structural defaults
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
    st.session_state.transcript = ''
    st.session_state.ai_guidance = "Simulation clean slate achieved. Memory registers completely purged."
    st.session_state.blueprint_generated = False

# Session variables fail-safe initialization
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial statement."
if 'blueprint_generated' not in st.session_state: st.session_state.blueprint_generated = False

# SIDEBAR CONTROLS
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Reset Simulation State", use_container_width=True):
    execute_hard_reset()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 🔍 Live Context Injection")
web_context_input = st.sidebar.text_area("Public Corporate Profile Context:", height=150, placeholder="Inject manual environment data here...", key="web_ctx_static")

# CLEAN & SCENARIO-AGNOSTIC ANALYSIS ENGINE
def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text or client is None:
        return "No text input captured."

    prompt_analyse = (
        f"Current Interview Stage: {current_stage}\n"
        f"Manual Web Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State: {json.dumps(st.session_state.slots)}\n"
        f"Current Psychological Tags: {json.dumps(st.session_state.tags)}\n\n"
        "TASK:\n"
        "Analyze the input. Extract factual data matching the slots and tags without inventing contexts.\n"
        "If the input lacks data for a key, or explicitly avoids giving structured specs, leave it 'Empty'.\n"
        "Format your answer strictly as a JSON object containing keys: 'slots' and 'tags' and 'ai_guidance'."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_analyse}
            ],
            temperature=0.0
        )
        result = json.loads(response.choices[0].message.content)
        
        # Write clean data back to session state
        incoming_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in incoming_slots:
                val = str(incoming_slots[key]).strip()
                if val not in ["", "None", "null", "undefined"]:
                    st.session_state.slots[key] = val
                    
        incoming_tags = result.get("tags", {})
        for key in st.session_state.tags:
            if key in incoming_tags:
                val_tag = str(incoming_tags[key]).strip()
                if val_tag not in ["", "null", "undefined"]:
                    st.session_state.tags[key] = val_tag

        return result.get("ai_guidance", "Turn parsed successfully.")
    except Exception as e:
        return f"Error analyzing input: {e}"

# UI VIEWPORT
st.markdown(f"### 💬 Interview Progress: Step {st.session_state.stage} / 4")
stage_questions = {
    "1": "Who am I speaking with today, what is the scale of your organization, and what corporate trigger brought you here?",
    "2": "What does your current software infrastructure look like? Are your daily workflows mostly manual or cloud-based?",
    "3": "Where are your teams losing the most hours, and if we deployed AI tomorrow, what are your core operational fears or constraints?",
    "4": "Reviewing your strategic situation: Here is what we know. Do you want to add, modify, or complete any data before receiving your final custom blueprint?"
}
st.subheader(f"👉 {stage_questions[str(st.session_state.stage)]}")

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"Smart Companion Strategy Insight: {st.session_state.ai_guidance}")
    
    # We use stage variable inside the key to ensure the text field is clean on reset
    manual_input = st.text_area("✍️ Saisie de l'entretien (Prospect Input):", height=120, key=f"input_stage_{st.session_state.stage}")
    
    if st.button("⚡ Analyze and Validate Input"):
        if manual_input:
            st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            st.rerun()
            
    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
                st.session_state.blueprint_generated = False
                st.rerun()
    with nav_col2:
        if st.session_state.stage < 4:
            if st.button("➡️ Next Stage"):
                st.session_state.stage += 1
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Parameters (Slots)")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Psychological Profiling")
    for tag_name, label in [("Lens", "Decision Filter (Lens)"), ("TechMaturity", "Tech Maturity"), ("Fear", "Identified Core Fear"), ("Verbatims", "Voice/Verbatim Mirror")]:
        tag_val = st.session_state.tags.get(tag_name, 'Standard')
        b_class = "status-box-filled" if tag_val not in ["Standard", "None", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{b_class}'><b>{label}:</b> {tag_val}</div>", unsafe_allow_html=True)

# 3. STRATEGIC GATEKEEPER COMPLIANCE GATE (STRICTLY ACTION-BOUND)
if st.session_state.stage == 4:
    st.markdown("---")
    st.subheader("🛡️ Strategic Gatekeeper Blueprint Compilation Control")
    
    filled_count = sum(1 for val in st.session_state.slots.values() if val != "Empty")
    
    if filled_count >= 3:
        if st.button("🎯 Compile Custom Strategic Blueprint", type="primary", use_container_width=True):
            st.session_state.blueprint_generated = True
            st.rerun()
    else:
        st.warning("🛑 Blueprint locked: The slots matrix requires at least 3 valid operational parameters in memory to pass the security gate.")

    if st.session_state.blueprint_generated and filled_count >= 3:
        st.header("📋 Comprehensive Strategic Blueprint")
        # Blueprint dynamic generation code executes strictly here...
        st.info("Dynamic blueprint output matching explicitly captured variables is ready.")
