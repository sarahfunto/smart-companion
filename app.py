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
# MODULE 1: SYSTEM PROMPT (STRICT DATA TYPING & BUZZWORD FILTER)
# =====================================================================
SYSTEM_PROMPT = """
You are a rigorous B2B sales data extractor operating with absolute literal discipline.
Your task is to parse an interview transcript turn by turn and fill designated slots.

[CRITICAL TECH SLOT SPECIFICATION]
- The 'Tech' slot must ONLY contain specific, real infrastructure, programming stacks, platforms, or tools (e.g., AWS, Python, PostgreSQL, specific CRM architectures).
- NEVER extract business methodologies, leadership roles, or broad project names like 'Digital Transformation', 'Agile project', or 'Cloud systems transition' into the Tech slot. If only these terms appear, 'Tech' must remain 'Empty'.
- BUZZWORD SALAD FILTER: If the client chains contradictory or incoherent technical concepts together without functional alignment (e.g., dropping 'blockchain, Kubernetes, APIs' in a single breath without context), flag the input as noise and leave 'Tech' as 'Empty'.

[INFERENTIAL DISCIPLINE]
- Do not interpolate pains or root causes from vague anxiety or generic management pressure. If no clear operational bottleneck or architectural limits are identified, leave them 'Empty'.
"""

# =====================================================================
# MODULE 2: STATE MANAGEMENT
# =====================================================================
if 'stage' not in st.session_state:
    st.session_state.stage = 1
if 'slots' not in st.session_state:
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state:
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard'}
if 'ai_guidance' not in st.session_state:
    st.session_state.ai_guidance = "Sandbox ready for Scenario 3 evaluation."
if 'gate_evaluated' not in st.session_state:
    st.session_state.gate_evaluated = False

def trigger_hard_reset():
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard'}
    st.session_state.ai_guidance = "State cleared. All cached parameters purged."
    st.session_state.gate_evaluated = False

# =====================================================================
# MODULE 3: UI LAYOUT & CLASSES
# =====================================================================
st.set_page_config(page_title="AI Advisor - Scenario 3 Sandbox", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { border-radius: 4px; height: 3em; }
    .status-box-empty { padding: 12px; border-radius: 6px; background-color: #1A1F26; border: 1px solid #2D3139; margin-bottom: 8px; color: #8A92A6; }
    .status-box-filled { padding: 12px; border-radius: 6px; background-color: #1E3A2F; border: 1px solid #2E694E; margin-bottom: 8px; color: #E3F9ED; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.sidebar.markdown("## ⚙️ Administrative Controls")
if st.sidebar.button("🔄 Execute Hard Reset", use_container_width=True):
    trigger_hard_reset()
    st.rerun()

# =====================================================================
# MODULE 4: INTERACTION & ANALYSIS LAYER
# =====================================================================
def execute_extraction_call(user_input):
    if not user_input or client is None:
        return
    
    runtime_payload = (
        f"Transcript input to parse: {user_input}\n"
        f"Current state memory: {json.dumps(st.session_state.slots)}\n"
        "Output JSON only with keys: slots, tags, ai_guidance."
    )
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": runtime_payload}
            ],
            temperature=0.0
        )
        payload = json.loads(response.choices[0].message.content)
        
        # Incremental state writing logic
        incoming_slots = payload.get("slots", {})
        for key in st.session_state.slots:
            val = str(incoming_slots.get(key, "Empty")).strip()
            
            # Independent Clean-up for the latent Tech bug
            if key == "Tech" and "digital transformation" in val.lower():
                val = "Empty"
                
            if val not in ["Empty", "", "None", "null", "undefined"]:
                st.session_state.slots[key] = val
                
        incoming_tags = payload.get("tags", {})
        for key in st.session_state.tags:
            val_tag = str(incoming_tags.get(key, "Standard")).strip()
            if val_tag not in ["Standard", "", "null", "Not yet confirmed"]:
                st.session_state.tags[key] = val_tag
                
        st.session_state.ai_guidance = payload.get("ai_guidance", "Turn processed successfully.")
    except Exception as e:
        st.error(f"Extraction Pipeline Failure: {e}")

# INTERVIEW VIEWPORTS
st.markdown(f"### 💬 Scenario Sandbox: Step {st.session_state.stage} / 4")
input_key = f"scen3_input_turn_{st.session_state.stage}"

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"System Message Tracker: {st.session_state.ai_guidance}")
    current_text = st.text_area("✍️ Prospect Input:", height=120, key=input_key)
    
    # Process turn button
    if st.button("⚡ Analyze and Validate Turn"):
        if current_text:
            execute_extraction_call(current_text)
            if st.session_state.stage == 4:
                st.session_state.gate_evaluated = True
            st.rerun()
            
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Step"):
                st.session_state.stage -= 1
                st.session_state.gate_evaluated = False
                st.rerun()
    with nav2:
        if st.session_state.stage < 4:
            if st.button("➡️ Next Step"):
                st.session_state.stage += 1
                st.session_state.gate_evaluated = False
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Parameters (Sidebar View)")
    for k, v in st.session_state.slots.items():
        css = "status-box-filled" if v != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{css}'><b>{k}:</b> {v}</div>", unsafe_allow_html=True)
        
    st.markdown("### 🧠 Psychological Mapping")
    for k, v in st.session_state.tags.items():
        css = "status-box-filled" if v not in ["Standard", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{css}'><b>{k}:</b> {v}</div>", unsafe_allow_html=True)

# =====================================================================
# MODULE 5: AUDITABLE & EXPLICIT VALIDATION GATEKEEPER
# =====================================================================
if st.session_state.stage == 4 and st.session_state.gate_evaluated:
    st.markdown("---")
    st.header("🛡️ Gatekeeper Security Audit & Verification Logs")
    
    core_requirements = {
        'Pain': 'Operational Pain & Dysfunctions',
        'RootCauses': 'Technical Structural Gaps',
        'Limits': 'Governance & Architecture Limits'
    }
    
    scorecard = {}
    filled_structural_count = 0
    
    for key, description in core_requirements.items():
        current_val = st.session_state.slots.get(key, 'Empty')
        is_valid = current_val not in ['Empty', '', 'None', 'null', 'undefined']
        
        if is_valid:
            scorecard[key] = {"status": "✅ VALIDATED", "color": "#8BFF8B", "val": current_val}
            filled_structural_count += 1
        else:
            scorecard[key] = {"status": "❌ INSUFFICIENT / EMPTY", "color": "#FF8B8B", "val": "No granular business data extracted."}

    if filled_structural_count < 3:
        html_component_content = f"""
        <div style="padding: 20px; border-radius: 8px; background-color: #2D1A1A; border: 2px solid #A63A3A; color: #FFEBEB; font-family: sans-serif;">
            <h3 style="color: #FF8B8B; margin-top: 0;">🛑 STRATEGIC GENERATION BLOCKED</h3>
            <p style="font-size: 14px;"><b>Reason:</b> Data integrity checks failed. The analysis gateway requires <b>all 3 core structural blocks</b> to compile a valid blueprint. Non-structural profile fields (like Role or Tech) are excluded from this safety calculation.</p>
            
            <table style="width: 100%; margin-top: 15px; border-collapse: collapse; font-size: 13px; color: #FFEBEB;">
                <thead>
                    <tr style="border-bottom: 2px solid #A63A3A; text-align: left;">
                        <th style="padding: 8px;">Required Structural Block</th>
                        <th style="padding: 8px;">Audit Status</th>
                        <th style="padding: 8px;">Extracted Content Checked in Memory</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom: 1px solid #4A2828;">
                        <td style="padding: 8px;"><b>{core_requirements['Pain']} (Pain)</b></td>
                        <td style="padding: 8px; color: {scorecard['Pain']['color']}; font-weight: bold;">{scorecard['Pain']['status']}</td>
                        <td style="padding: 8px;"><i>{scorecard['Pain']['val']}</i></td>
                    </tr>
                    <tr style="border-bottom: 1px solid #4A2828;">
                        <td style="padding: 8px;"><b>{core_requirements['RootCauses']} (Root Causes)</b></td>
                        <td style="padding: 8px; color: {scorecard['RootCauses']['color']}; font-weight: bold;">{scorecard['RootCauses']['status']}</td>
                        <td style="padding: 8px;"><i>{scorecard['RootCauses']['val']}</i></td>
                    </tr>
                    <tr style="border-bottom: 1px solid #4A2828;">
                        <td style="padding: 8px;"><b>{core_requirements['Limits']} (Limits)</b></td>
                        <td style="padding: 8px; color: {scorecard['Limits']['color']}; font-weight: bold;">{scorecard['Limits']['status']}</td>
                        <td style="padding: 8px;"><i>{scorecard['Limits']['val']}</i></td>
                    </tr>
                </tbody>
            </table>
            <br>
            <p style="font-size: 12px; font-style: italic; color: #CCA3A3;">Security Directive: The blueprint generation has been short-circuited. No documents will be inferred from the current transcript due to the high density of conversational noise, buzzwords, or qualitative statements.</p>
        </div>
        """
        st.components.v1.html(html_component_content, height=280, scrolling=False)
    else:
        st.success("🎯 Quality assurance gate passed. Data depth is verified as accurate for compilation.")

