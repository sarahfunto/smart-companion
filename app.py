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
# MODULE 1: SYSTEM PROMPT ARCHITECTURE (MODULAR & ANTI-JARGON)
# =====================================================================
SYSTEM_PROMPT = """
You are an expert B2B sales psychologist and senior enterprise consultant acting with absolute inferential discipline.

[STRICT INFERENTIAL DISCIPLINE]
- NEVER infer corporate slots from generalities or evasive answers.
- If the client actively avoids giving specifics about their company size (e.g., using terms like 'in-between', 'not huge, not small', 'decent-sized outfit', 'hard to say'), you are strictly forbidden from mapping this to 'Medium' or any categorical value. You must leave the field as 'Empty'.
- Only extract 'Pain', 'RootCauses', or 'Limits' if concrete, actionable technical or structural details are explicitly provided.

[STRATEGIC SOBRIETY & ANTI-JARGON]
- Never leak or output internal technical words like 'mirroring', 'structural feeling', 'slots', 'verbatims', or 'psychological tags' inside the generated text.
- Do not use empty consulting cliches ('chart a path forward', 'acknowledging dynamics'). Keep prose direct, structural, and executive-ready.
"""

# =====================================================================
# MODULE 2: STATE MANAGEMENT (HERMETIC RESET)
# =====================================================================
def reset_entire_simulation():
    st.session_state.stage = 1
    st.session_state.slots = {
        'Role': 'Empty', 
        'CompanySize': 'Empty', 
        'Tech': 'Empty', 
        'Pain': 'Empty', 
        'RootCauses': 'Empty', 
        'Limits': 'Empty'
    }
    st.session_state.tags = {
        'Lens': 'Standard', 
        'Fear': 'Not yet confirmed', 
        'TechMaturity': 'Standard', 
        'Verbatims': 'None'
    }
    st.session_state.transcript = ''
    st.session_state.ai_guidance = "Simulation reset successfully. All parameters are cleared."

# Initialize safely on first load
if 'slots' not in st.session_state or 'stage' not in st.session_state:
    reset_entire_simulation()

# =====================================================================
# MODULE 3: UI & STYLES
# =====================================================================
st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    
    .status-box-empty { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #1E2329; 
        border: 1px solid #3E444B; 
        margin-bottom: 8px; 
        color: #6C757D;
    }
    
    .status-box-filled { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #155724; 
        border: 2px solid #28a745; 
        margin-bottom: 8px; 
        color: #D4EDDA;
        font-weight: bold;
    }
    
    .recommendation-box {
        padding: 25px;
        border-radius: 15px;
        background-color: #0B2545;
        border: 2px solid #134074;
        color: #EEF4F8;
        margin-top: 15px;
        margin-bottom: 20px;
        line-height: 1.6;
    }

    .priority-badge-high {
        display: inline-block;
        background-color: #E63946;
        color: white;
        padding: 6px 14px;
        font-size: 0.85em;
        font-weight: bold;
        border-radius: 4px;
        letter-spacing: 1px;
        margin-bottom: 15px;
    }
    
    .gatekeeper-error-box {
        padding: 25px;
        border-radius: 15px;
        background-color: #3A1C1C;
        border: 2px solid #C94A4A;
        color: #F8EEEE;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# SIDEBAR CONTROLS
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Réinitialiser la simulation (Reset Hermétique)", use_container_width=True):
    reset_entire_simulation()
    st.rerun()

st.sidebar.markdown("---")
web_context_input = st.sidebar.text_area("📝 Corporate Profile / Web Context", height=150)

# =====================================================================
# MODULE 4: ISOLATED PARSING ENGINE (SCENARIO-AWARE CONTRAINTS)
# =====================================================================
def analyze_input_engine(user_text, context_web, current_stage):
    if not user_text:
        return None

    prompt_analyse = (
        f"Current Interview Stage: {current_stage}\n"
        f"Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State: {json.dumps(st.session_state.slots)}\n"
        f"Current Psychological Tags: {json.dumps(st.session_state.tags)}\n\n"
        "Extract slots and tags according to the system rules. Respond ONLY in structured JSON with keys: slots, tags, ai_guidance."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_analyse}
            ],
            temperature=0.1
        )
        result = json.loads(response.choices[0].message.content)
        
        new_slots = result.get("slots", {})
        new_tags = result.get("tags", {})

        # --- SCENARIO 2 CRITICAL ANTI-EVASION GUARDRAILS ---
        user_text_lower = user_text.lower()
        evasive_keywords = ["in-between", "not huge", "not small", "decent-sized", "wear a lot of hats", "hard to say"]
        
        # Check for evasion on company size
        is_evasive_size = any(x in user_text_lower for x in evasive_keywords)
        
        # Safe Slot Update with Anti-Evasion Override
        for key in st.session_state.slots:
            if key == "CompanySize" and is_evasive_size:
                st.session_state.slots[key] = "Empty"  # Force empty to block false positives
            elif key in new_slots:
                val = str(new_slots[key]).strip()
                if val not in ["Empty", "", "None", "null", "undefined"]:
                    st.session_state.slots[key] = val
        
        # Safe Tags Update
        for tag_key in st.session_state.tags:
            if tag_key in new_tags:
                val_tag = str(new_tags[tag_key]).strip()
                if val_tag not in ["", "null"]:
                    st.session_state.tags[tag_key] = val_tag

        return result.get("ai_guidance", "Analysis complete.")
    except Exception as e:
        return f"Error analyzing input: {e}"

# INTERVIEW INTERFACE DISPLAY
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
    guidance_text = st.session_state.get('ai_guidance', "Welcome to the simulation.")
    st.info(f"Smart Companion Strategy Insight: {guidance_text}")
    
    input_key = f"client_input_stage_{st.session_state.stage}"
    manual_input = st.text_area("⌨️ Client Input:", height=100, key=input_key)
    
    if st.button("⚡ Validate and Analyze Input"):
        if manual_input:
            st.session_state.transcript = manual_input
            st.session_state['ai_guidance'] = analyze_input_engine(manual_input, web_context_input, st.session_state.stage)
            st.rerun()
            
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
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
    for tag_name, label in [("Lens", "Decision Filter (Lens)"), ("TechMaturity", "Tech Maturity"), ("Fear", "Identified Core Fear")]:
        tag_val = st.session_state.tags.get(tag_name, 'Standard')
        b_class = "status-box-filled" if tag_val not in ["Standard", "None", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{b_class}'><b>{label}:</b> {tag_val}</div>", unsafe_allow_html=True)

# =====================================================================
# MODULE 5: SECURITY GATEKEEPER & FINAL OUTPUT CONTROL
# =====================================================================
if st.session_state.stage == 4:
    st.markdown("---")
    st.header("📋 Analysis Gateway Assessment")
    
    # Strict evaluation of high-value diagnostic requirements
    filled_core_slots = 0
    for critical_key in ['Pain', 'RootCauses', 'Limits']:
        current_value = st.session_state.slots.get(critical_key, 'Empty')
        if current_value not in ['Empty', '', 'None', 'null']:
            filled_core_slots += 1
            
    # CRITICAL GATEKEEPER CHECK (SILENT REFUSAL PRINCIPLE)
    if filled_core_slots < 3:
        st.markdown(f"""
        <div class="gatekeeper-error-box">
            <h4 style="color: #C94A4A; margin-top:0;">🛑 STRATEGIC GATEKEEPER: DISCOVERY DATA INSUFFICIENT</h4>
            <p><b>Status:</b> Generation Blocked (Core parameters filled: {filled_core_slots} / 3 required).</p>
            <p>The client has deployed evasive language or non-specific summaries. Generating a blueprint at this stage would force programmatic hallucination and violate professional sobriety rules.</p>
            <p><i>Action required: Return to previous stages to capture precise technical dysfunctions, governance limits, or explicit operational pains.</i></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Proceed with generating the Blueprint ONLY if security criteria are fully met
        with st.spinner("Generating deep mirrored diagnostic reflecting human stakes..."):
            prompt_final = f"""
            Act as an elite B2B Sales Psychologist. Profile details:
            - Slots: {json.dumps(st.session_state.slots)}
            - Tags: {json.dumps(st.session_state.tags)}
            Generate the full enterprise blueprint report following the strict sober guidelines.
            """
            try:
                final_diag = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_final}],
                    temperature=0.0
                ).choices[0].message.content
                st.markdown(final_diag)
            except Exception as e:
                st.error(f"Error: {e}")
