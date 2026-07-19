import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# =====================================================================
# MODULE 1: SYSTEM PROMPT (PURE EXTRACTION - NO POST-PROCESSING)
# =====================================================================
SYSTEM_PROMPT = """
You are a B2B sales data extractor operating with absolute, literal discipline. 
Your unique task is to populate a structured profile from a raw interview transcript.

[RULES OF INFERENTIAL DISCIPLINE]
1. DO NOT INFER OR EXTRAPOLATE: If the client does not name a specific technology, tool, software, or clear architectural framework, 'Tech' must be 'Empty'.
2. ANTI-EVASION: If the client uses non-specific corporate phrases or avoidance language (e.g., 'we wear a lot of hats', 'people are tired', 'not huge, not small, in-between', 'some older systems'), you must NOT map this to categories like 'Medium', 'Hybrid' or create operational recommendations. Leave the respective field strictly as 'Empty'.
3. NO PLACEMARKERS: Do not invent data to be helpful. If a pain, root cause, or operational limit is not explicitly and technically defined, the slot value must remain 'Empty'.

You must respond ONLY with a valid JSON object matching this exact structure:
{
  "slots": {
    "Role": "Value or 'Empty'",
    "CompanySize": "Value or 'Empty'",
    "Tech": "Value or 'Empty'",
    "Pain": "Value or 'Empty'",
    "RootCauses": "Value or 'Empty'",
    "Limits": "Value or 'Empty'"
  },
  "tags": {
    "Lens": "Commercial, Technical, or 'Standard'",
    "Fear": "Explicitly stated fear or 'Not yet confirmed'",
    "TechMaturity": "High, Low, or 'Standard'"
  },
  "ai_guidance": "A brief, highly sober sentence describing what data is missing."
}
"""

# =====================================================================
# MODULE 2: ENCAPSULATED STATE MANAGEMENT
# =====================================================================
if 'stage' not in st.session_state:
    st.session_state.stage = 1
if 'slots' not in st.session_state:
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state:
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard'}
if 'ai_guidance' not in st.session_state:
    st.session_state.ai_guidance = "Initial state ready. Enter data to begin."

def trigger_hard_reset():
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard'}
    st.session_state.ai_guidance = "Simulation completely cleared. Ready for fresh scenario."

# =====================================================================
# MODULE 3: UI ARCHITECTURE
# =====================================================================
st.set_page_config(page_title="AI Advisor - Verification Sandbox", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { border-radius: 4px; height: 3em; }
    .status-box-empty { padding: 12px; border-radius: 6px; background-color: #1A1F26; border: 1px solid #2D3139; margin-bottom: 8px; color: #8A92A6; }
    .status-box-filled { padding: 12px; border-radius: 6px; background-color: #1E3A2F; border: 1px solid #2E694E; margin-bottom: 8px; color: #E3F9ED; font-weight: bold; }
    .gatekeeper-block { padding: 25px; border-radius: 8px; background-color: #2D1A1A; border: 2px solid #A63A3A; color: #FFEBEB; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.markdown("## ⚙️ Administrative Controls")
if st.sidebar.button("🔄 Executer un Reset Étanche (P0)", use_container_width=True):
    trigger_hard_reset()
    st.rerun()

# =====================================================================
# MODULE 4: PIPELINE ANALYSIS ENGINE
# =====================================================================
def execute_extraction_call(user_input):
    if not user_input or client is None:
        return
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this specific turn: {user_input}"}
            ],
            temperature=0.0  # Absolute determinism
        )
        payload = json.loads(response.choices[0].message.content)
        
        # Incremental update logic with structural verification
        incoming_slots = payload.get("slots", {})
        for key in st.session_state.slots:
            val = str(incoming_slots.get(key, "Empty")).strip()
            if val not in ["Empty", "", "None", "null", "undefined"]:
                st.session_state.slots[key] = val
                
        incoming_tags = payload.get("tags", {})
        for key in st.session_state.tags:
            val_tag = str(incoming_tags.get(key, "Standard")).strip()
            if val_tag not in ["Standard", "", "null", "Not yet confirmed"]:
                st.session_state.tags[key] = val_tag
                
        st.session_state.ai_guidance = payload.get("ai_guidance", "Processing complete.")
    except Exception as e:
        st.error(f"Execution Error: {e}")

# INTERVIEW WORKFLOW DISPLAY
st.markdown(f"### 💬 Active Simulation: Step {st.session_state.stage} / 4")
input_key = f"raw_input_turn_{st.session_state.stage}"

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"Extractor Insight: {st.session_state.ai_guidance}")
    current_text = st.text_area("✍️ Insert Client Statement:", height=120, key=input_key)
    
    if st.button("⚡ Process Statement through Extraction Layer"):
        if current_text:
            execute_extraction_call(current_text)
            st.rerun()
            
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Step Back"):
                st.session_state.stage -= 1
                st.rerun()
    with nav2:
        if st.session_state.stage < 4:
            if st.button("➡️ Advance Step"):
                st.session_state.stage += 1
                st.rerun()

with col2:
    st.markdown("### 📊 Active Memory Slots")
    for k, v in st.session_state.slots.items():
        css = "status-box-filled" if v != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{css}'><b>{k}:</b> {v}</div>", unsafe_allow_html=True)
        
    st.markdown("### 🧠 Active Psychological Tags")
    for k, v in st.session_state.tags.items():
        css = "status-box-filled" if v not in ["Standard", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{css}'><b>{k}:</b> {v}</div>", unsafe_allow_html=True)

# =====================================================================
# MODULE 5: HARD CODED PYTHON GATEKEEPER (ZERO-TRUST SECURITY CHIP)
# =====================================================================
if st.session_state.stage == 4:
    st.markdown("---")
    st.header("🛡️ Security Gateway Validation")
    
    # Mathematical calculation of real core data points present in state
    valid_business_points = 0
    for structural_key in ['Pain', 'RootCauses', 'Limits']:
        stored_value = st.session_state.slots.get(structural_key, 'Empty')
        if stored_value not in ['Empty', '', 'None', 'null', 'undefined']:
            valid_business_points += 1
            
    # ABSOLUTE HARD-GATE RULE (Executed in Python, cannot be bypassed by LLM behavior)
    if valid_business_points < 3:
        st.markdown(f"""
        <div class="gatekeeper-block">
            <h3 style="color: #FF8B8B; margin-top: 0;">🛑 DISCOVERY GATEKEEPER BLOCK: INSUFFICIENT DATA</h3>
            <p><b>Validation Metric:</b> {valid_business_points} / 3 mandatory operational criteria met.</p>
            <p><b>Security Directive:</b> The strategy engine has refused to execute the generation pipeline. The input history consists primarily of structural noise, evasive syntax, or unverified qualitative descriptions.</p>
            <p><i>To generate an executive blueprint, discovery must capture explicit technical pains, defined structural gaps, and explicit architectural or administrative limitations. No speculative consulting documents can be mapped from current state.</i></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.success("✅ Criteria met. Ready to compile validated blueprint.")
        # Only here would the final generation prompt execute if this were a production run.

