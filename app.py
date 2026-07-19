import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# SYSTEM PROMPT FOCUSING EXCLUSIVELY ON RAW DATA EXTRACTION WITH NO SCENARIO BIAS
SYSTEM_PROMPT = """
You are a rigorous, literal B2B sales data extractor operating with strict inferential discipline. 
Your sole objective is to parse the latest client transcript turn and populate the target slots and psychological tags based ONLY on explicit facts provided.

[CRITICAL INFERENTIAL DIRECTIVES]
1. ZERO INFERENCE ON UNMENTIONED TOOLS: Never invent software names, brands, or platforms. If the client mentions HubSpot or PostgreSQL, map them exactly. For unmentioned tools, use strictly generic definitions like 'existing CRM tools' or 'internal databases'. Never suggest migrations to tools like Zoho or Pipedrive unless requested. Focus on 'bridging ecosystems, not replacing'.
2. COMPANY SIZE RULE: If the prospect provides a specific number of employees (e.g., '11 employees') or an explicit size, map it directly to 'CompanySize'. If the prospect is vague, evasive, or explicitly avoids giving a precise metric or definitive scale (e.g., saying 'not huge, not small, in-between'), leave 'CompanySize' as 'Empty'.
3. ACCURATE VERBATIMS: Extract exact phrases or strong emotional markers used by the prospect (e.g., 'wearing many hats', 'people are tired', 'founder refuses to abandon Access').

Output strictly as a JSON object containing keys: slots (Role, CompanySize, Tech, Pain, RootCauses, Limits), tags (Fear, Verbatims), ai_guidance.
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

# BULLETPROOF RE-INITIALIZATION MECHANISM
def execute_hard_reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
    st.session_state.tags = {'Fear': 'Not yet confirmed', 'Verbatims': 'None'}
    st.session_state.transcript = ''
    st.session_state.ai_guidance = "Simulation state completely reset. All parameter blocks cleared."
    st.session_state.blueprint_generated = False

if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Fear': 'Not yet confirmed', 'Verbatims': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial statement."
if 'blueprint_generated' not in st.session_state: st.session_state.blueprint_generated = False

# SIDEBAR SIMULATION LAYER
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Reset Simulation State", use_container_width=True):
    execute_hard_reset()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 🔍 Live Context Injection")
web_context_input = st.sidebar.text_area("Public Corporate Profile Context:", height=150, placeholder="Inject manual environment data here...", key="web_ctx_static")

# DECOUPLED CLASSIFICATION LOGIC FOR METADATA
def classify_decision_lens(slots_data, transcript_data):
    combined = (str(slots_data.get('Pain', '')) + " " + str(slots_data.get('RootCauses', '')) + " " + transcript_data).lower()
    commercial_keywords = ['renewal', 'revenue', 'board', 'forecast', 'pipeline', 'churn', 'sales', 'budget', 'employee']
    if any(kw in combined for kw in commercial_keywords):
        return "Commercial / Revenue-Driven"
    return "Standard"

def classify_technology_profile(slots_data):
    tech_str = str(slots_data.get('Tech', '')).lower()
    limits_str = str(slots_data.get('Limits', '')).lower()
    
    has_modern = any(m in tech_str for m in ['hubspot', 'saas', 'slack', 'sheets', 'cloud'])
    has_legacy = any(l in tech_str or l in limits_str for l in ['postgresql', 'access', 'legacy', 'database'])
    
    if has_modern and has_legacy:
        return "Hybrid Stack – Modern SaaS with Legacy Database dependency"
    elif has_modern:
        return "Modern SaaS Stack"
    elif has_legacy:
        return "Legacy Infrastructure Stack"
    return "Standard"

def infer_transformation_strategy(slots_data):
    filled_count = sum(1 for val in slots_data.values() if val != "Empty")
    tech_str = str(slots_data.get('Tech', '')).lower()
    pain_str = str(slots_data.get('Pain', '')).lower()
    
    if filled_count >= 4 and ('hubspot' in tech_str or 'postgresql' in tech_str or 'renewal' in pain_str or 'pipeline' in pain_str):
        return "Incremental Modernization & Ecosystem Bridging"
    return "Discovery & Architecture Mapping"

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
        "Extract raw factual metrics matching keys. Pay close attention to numbers for CompanySize.\n"
        "Format response as a JSON object with keys: slots, tags, ai_guidance."
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

# Dynamically compute decoupled metadata on the fly
derived_lens = classify_decision_lens(st.session_state.slots, st.session_state.transcript)
derived_tech_profile = classify_technology_profile(st.session_state.slots)
derived_strategy = infer_transformation_strategy(st.session_state.slots)

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"Smart Companion Strategy Insight: {st.session_state.ai_guidance}")
    
    manual_input = st.text_area("✍️ Prospect Input (Type what the client says):", height=120, key=f"input_stage_{st.session_state.stage}")
    
    if st.button("⚡ Analyze and Validate Input"):
        if manual_input:
            st.session_state.transcript += "\\n" + manual_input
            st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            st.rerun()
        else:
            st.warning("Please type the prospect input before running analysis pipelines.")
            
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
                st.session_state.blueprint_generated = False
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Parameters (Slots)")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Decoupled Psychological Profiling")
    
    # Display Decoupled Metadata Fields
    box_lens = "status-box-filled" if derived_lens != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{box_lens}'><b>Decision Filter (Lens):</b> {derived_lens}</div>", unsafe_allow_html=True)
    
    box_tech = "status-box-filled" if derived_tech_profile != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{box_tech}'><b>Tech Profile:</b> {derived_tech_profile}</div>", unsafe_allow_html=True)
    
    for tag_name, label in [("Fear", "Identified Core Fear"), ("Verbatims", "Voice/Verbatim Mirror")]:
        tag_val = st.session_state.tags.get(tag_name, 'Standard')
        b_class = "status-box-filled" if tag_val not in ["Standard", "None", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{b_class}'><b>{label}:</b> {tag_val}</div>", unsafe_allow_html=True)

# STRATEGIC GATEKEEPER COMPLIANCE BLUEPRINT COMPILATION
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
        st.header(f"📋 Comprehensive Strategic Blueprint — [Strategy: {derived_strategy}]")
        
        with st.spinner("Compiling mirrored architecture diagnostic documentation..."):
            prompt_final = f"""
            Act as an elite B2B Sales Psychologist and Enterprise Management Consultant.
            Generate a custom business architecture report matching the client's concrete metrics.

            - Role: {st.session_state.slots['Role']}
            - Company Size: {st.session_state.slots['CompanySize']}
            - Technical Stack (Tech): {st.session_state.slots['Tech']}
            - Core Pain (Pain): {st.session_state.slots['Pain']}
            - Critical Structural Gaps (Root Causes): {st.session_state.slots['RootCauses']}
            - Extracted Constraints & Political Limits (Limits): {st.session_state.slots['Limits']}
            - Calculated Decision Filter (Lens): {derived_lens}
            - Calculated Tech Profile: {derived_tech_profile}
            - Extracted Fear (The Personal Stakes): {st.session_state.tags.get('Fear', 'None')}
            - Captured Verbatims / Client Metaphors: {st.session_state.tags.get('Verbatims', 'None')}
            - Target Strategy: {derived_strategy}

            REPORT STRATEGIC MANDATES:
            1. BRIDGE, DO NOT REPLACE: Validate that the existing stack components are structurally sound, but lacking visibility interfaces. Explicitly treat tools like Microsoft Access as immutable business rules: write recommendations around 'preserving the existing Microsoft Access layer as a required legacy dependency while minimizing its operational friction through zero-loss database integration' rather than suggesting updating or modernizing it directly.
            2. CLIENT-READY BUSINESS HEADINGS: Write the report using clear business headers targeted to a decision maker. Use these exact titles for the strategic pillars:
               - Revenue Protection Strategy
               - Core Architectural Principles
               - Ecosystem Integration Priorities
            3. NO EXTERNAL SOLUTION INFERENCES: Focus on fixing the visibility bridge between the current systems. Never introduce unauthorized vendor names.
            """
            
            try:
                final_diag = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_final}],
                    temperature=0.0
                ).choices[0].message.content

                st.markdown(f"""
                <div class="recommendation-box">
                    <div class="priority-badge-high">⚠️ ADAPTIVE RISK LEVEL: HIGH</div>
                    <div style="font-size: 0.9em; margin-top: -10px; color: #FFD2D2;">
                        <b>Human & Corporate Posture Risk Assessment:</b><br>
                        • <b>Strategic Path:</b> Determined as <b>{derived_strategy}</b>.<br>
                        • <b>Ecosystem Directive:</b> Bridge reporting data pipelines into the primary workspace natively rather than initiating system overhauls. Preserve core architecture dependencies exactly as specified by organizational rules.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(final_diag)
                
                st.subheader("Final Summary Matrix")
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.markdown(f"""
                    * **Prospect Role:** {st.session_state.slots['Role']}
                    * **Company Size:** {st.session_state.slots['CompanySize']}
                    * **Decision Lens:** {derived_lens}
                    """)
                with col_m2:
                    st.markdown(f"""
                    * **Technology Profile:** {derived_tech_profile}
                    * **Transformation Strategy:** {derived_strategy}
                    """)
            except Exception as e:
                st.error(f"Error compiling document asset: {e}")
