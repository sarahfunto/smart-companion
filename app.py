import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# ADAPTIVE SYSTEM PROMPT WITH BUILT-IN STRATEGIC INTELLIGENCE
SYSTEM_PROMPT = """
You are an expert B2B sales psychologist and senior enterprise infrastructure consultant operating with absolute literal discipline.
Your job is to parse the latest client input, update parameters, and apply an adaptive evaluation framework based on data density.

[CRITICAL EXTRACTION DIRECTIVES]
1. ZERO INFERENCE ON UNMENTIONED TOOLS: Never invent software names, brands, or platforms. If the client mentions HubSpot or PostgreSQL, map them exactly. For unmentioned tools, use strictly generic definitions like 'existing CRM tools' or 'internal databases'. Never suggest migrations to tools like Zoho or Pipedrive unless requested. Focus on 'bridging ecosystems, not replacing'.
2. PRECISE TECH MATURITY & STACK PROFILE: 
   - If the client describes a split ecosystem (e.g., modern software interacting with siloed backend infrastructure), classify 'TechMaturity' as 'Hybrid Stack (Modern Cloud & Legacy Access Assets)'.
   - Only use 'Standard' or 'Empty' if no infrastructure details are provided.
3. ADAPTIVE DECISION FILTER (LENS):
   - Analyze the underlying business driver. If the dialogue explicitly focuses on renewal risk, revenue impacts, board expectations, or forecast pipeline errors, classify 'Lens' as 'Commercial / Revenue-Driven'.
4. COMPANY SIZE COMPLIANCE: If the client is intentionally vague or avoiding exact employee metrics (e.g., 'not huge, not small, in-between'), keep 'CompanySize' as 'Empty'. Do not default to 'Medium'.

Output strictly as a JSON object containing keys: slots (Role, CompanySize, Tech, Pain, RootCauses, Limits), tags (Lens, TechMaturity, Fear, Verbatims), ai_guidance.
"""

st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

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
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
    st.session_state.transcript = ''
    st.session_state.ai_guidance = "Simulation state completely reset. All parameter blocks cleared."
    st.session_state.blueprint_generated = False

if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
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
        "Extract factual structures matching keys. If parameters are explicitly commercial or revenue-impacting, "
        "ensure 'Lens' updates accurately. If technical configurations detail custom integrations with legacy databases, "
        "classify 'TechMaturity' as 'Hybrid Stack (Modern Cloud & Legacy Access Assets)'.\n"
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

# MAIN UI INTERACTION VIEWPORT
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
    
    manual_input = st.text_area("✍️ Prospect Input (Type what the client says):", height=120, key=f"input_stage_{st.session_state.stage}")
    
    if st.button("⚡ Analyze and Validate Input"):
        if manual_input:
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
        
    st.markdown("#### 🧠 Psychological Profiling")
    for tag_name, label in [("Lens", "Decision Filter (Lens)"), ("TechMaturity", "Tech Maturity"), ("Fear", "Identified Core Fear"), ("Verbatims", "Voice/Verbatim Mirror")]:
        tag_val = st.session_state.tags.get(tag_name, 'Standard')
        b_class = "status-box-filled" if tag_val not in ["Standard", "None", "Not yet confirmed"] else "status-box-empty"
        st.markdown(f"<div class='{b_class}'><b>{label}:</b> {tag_val}</div>", unsafe_allow_html=True)

# DYNAMIC & ADAPTIVE STRATEGIC BLUEPRINT GATE
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
        # HIGH CONFIDENCE EXTRACTION GATE (E.G., SCENARIO 1 DATA RICHNESS DETECTED)
        is_high_confidence = (
            st.session_state.slots['Pain'] != 'Empty' and 
            st.session_state.slots['RootCauses'] != 'Empty' and 
            ("commercial" in str(st.session_state.tags.get('Lens', '')).lower() or "hubspot" in str(st.session_state.slots.get('Tech', '')).lower() or "postgresql" in str(st.session_state.slots.get('Tech', '')).lower())
        )
        
        transformation_strategy = "Incremental Modernization & Ecosystem Bridging" if is_high_confidence else "Discovery & Architecture Mapping"
        
        st.header(f"📋 Comprehensive Strategic Blueprint — [Strategy: {transformation_strategy}]")
        
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
            - Decision Lens: {st.session_state.tags.get('Lens', 'Standard')}
            - Extracted Fear (The Personal Stakes): {st.session_state.tags.get('Fear', 'None')}
            - Captured Verbatims / Client Metaphors: {st.session_state.tags.get('Verbatims', 'None')}
            - Determined Transformation Strategy: {transformation_strategy}

            REPORT REQUIREMENTS:
            1. PERSIST AND ACCENTUATE THE CORE ECOSYSTEM: Do not suggest replacing existing software tools (like CRM architectures) with unrelated brands (e.g., Zoho, Pipedrive). The strategic mandate is to 'BRIDGE, NOT REPLACE'. Validate that the existing stack components are structurally sound, but lacking integration or real-time visibility interfaces.
            2. HIGH PERSONALITY ARCHITECTURE NARRATIVE: Avoid generic audit structures like 'Executive Summary'. Write using highly specific diagnostic pillars targeting the concrete pain points (e.g., 'Ecosystem Visibility Gaps', 'Pipeline and Renewal Exposure Risks', 'Targeted Revenue Acceleration Path').
            3. WEAVE EXACT CLIENT STAKES: Directly confront corporate board visibility pressure, renewal forecasts, and internal credibility risks without using leaked implementation jargon tokens.
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
                        • <b>Strategic Path:</b> Determined as <b>{transformation_strategy}</b>. The current ecosystem visibility gaps expose pipeline validation.<br>
                        • <b>Ecosystem Directive:</b> Maintain core structures. Bridge reporting data pipelines into the primary workspace natively rather than initiating unnecessary system overhauls.
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
                    * **Decision Lens:** {st.session_state.tags.get('Lens', 'Standard')}
                    """)
                with col_m2:
                    st.markdown(f"""
                    * **Technology Profile:** {st.session_state.tags.get('TechMaturity', 'Standard')}
                    * **Transformation Strategy:** {transformation_strategy}
                    """)
            except Exception as e:
                st.error(f"Error compiling document asset: {e}")
