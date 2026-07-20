import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# SYSTEM PROMPT FORCING JARGON FILTERING & PSYCHOLOGICAL ALIGNMENT
SYSTEM_PROMPT = """
You are a cold, literal B2B sales data extractor operating with absolute inferential discipline. 
Your sole objective is to parse the latest client transcript turn and populate the target slots and psychological tags based ONLY on explicit, concrete, verifiable facts.

[CRITICAL INFERENTIAL & STRUCTURAL DIRECTIVES]
1. TECH IMPOSTOR & JARGON FILTER: If a prospect drops technical terms (e.g., blockchain, Kubernetes, API, firewall) but explicitly admits to not understanding them, mixing them up, or lacking an engineering background, you MUST treat the technology stack as completely unverified and output "Unknown" for the Tech slot. Do not let speculative jargon pollute the data.
2. HOLISTIC PAIN EXTRACTION: When a prospect provides quantifiable business performance degradation (e.g., 'open rates down 12%') alongside systemic business outcomes (e.g., 'campaigns aren't converting'), you must capture BOTH elements cohesively within the Pain slot. Do not truncate the business impact.
3. ZERO INFERENCE OR GUESSTIMATING: General phrases, colloquialisms ('wear a lot of hats'), or conversational fillers mean "Unknown" for that specific slot. Do not extrapolate titles or sizes.
4. STRATEGIC INSIGHT PRIORITY: If a prospect uses contradictory jargon while experiencing measurable performance drops, your 'ai_guidance' field must explicitly direct the sales rep to ignore the ambiguous technical terminology and focus exclusively on the measurable business/marketing performance bottleneck.
5. CAUSE VS. CONSTRAINT STRUCTURE:
   - RootCauses must capture technical friction. If the tech stack is unverified ("Unknown"), the Root Cause must remain "Unknown".
   - Emotional anxiety, fear of looking incompetent to leadership, or generic competitive pressure belongs exclusively under Fear.

Output strictly as a JSON object containing keys: slots (Role, CompanySize, Tech, Pain, RootCauses, Limits), tags (Fear, Verbatims), ai_guidance.
"""

st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

# CSS Styling
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    .status-box-empty { padding: 12px; border-radius: 10px; background-color: #1E2329; border: 1px solid #3E444B; margin-bottom: 8px; color: #E2E8F0; font-style: italic; }
    .status-box-filled { padding: 12px; border-radius: 10px; background-color: #155724; border: 2px solid #28a745; margin-bottom: 8px; color: #D4EDDA; font-weight: bold; }
    .recommendation-box { padding: 25px; border-radius: 15px; background-color: #0B2545; border: 2px solid #134074; color: #EEF4F8; margin-top: 15px; margin-bottom: 20px; line-height: 1.6; }
    .priority-badge-high { display: inline-block; background-color: #E63946; color: white; padding: 6px 14px; font-size: 0.85em; font-weight: bold; border-radius: 4px; letter-spacing: 1px; margin-bottom: 15px; }
    .last-input-box { background-color: #1E2530; border-left: 4px solid #2E6BFF; padding: 12px; border-radius: 4px; margin-top: 15px; color: #A0AEC0; font-style: italic; font-size: 0.95em; }
    .lock-box { padding: 20px; background-color: #2A1215; border: 2px dashed #E63946; border-radius: 10px; color: #FFD2D2; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# BULLETPROOF RE-INITIALIZATION MECHANISM
def execute_hard_reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Unknown', 'CompanySize': 'Unknown', 'Tech': 'Unknown', 'Pain': 'Unknown', 'RootCauses': 'Unknown', 'Limits': 'Unknown'}
    st.session_state.tags = {'Fear': 'Unknown', 'Verbatims': 'None'}
    st.session_state.transcript = ''
    st.session_state.last_analyzed = ''
    st.session_state.ai_guidance = "Simulation state completely reset. Awaiting verified factual parameters."
    st.session_state.blueprint_generated = False
    st.session_state.step4_validated = False

if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Unknown', 'CompanySize': 'Unknown', 'Tech': 'Unknown', 'Pain': 'Unknown', 'RootCauses': 'Unknown', 'Limits': 'Unknown'}
if 'tags' not in st.session_state: st.session_state.tags = {'Fear': 'Unknown', 'Verbatims': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'last_analyzed' not in st.session_state: st.session_state.last_analyzed = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input explicit statement metrics."
if 'blueprint_generated' not in st.session_state: st.session_state.blueprint_generated = False
if 'step4_validated' not in st.session_state: st.session_state.step4_validated = False

# SIDEBAR SIMULATION LAYER
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Reset Simulation State", use_container_width=True):
    execute_hard_reset()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 🔍 Live Context Injection")
web_context_input = st.sidebar.text_area("Public Corporate Profile Context:", height=150, placeholder="Inject manual environment data here...", key="web_ctx_static")

# DETERMINISTIC DATA MATCHING LABELS
def classify_decision_lens(slots_data, transcript_data):
    role = str(slots_data.get('Role', '')).lower()
    transcript = transcript_data.lower()
    
    # Explicit detection of a technical impostor / business-only persona masquerading with jargon
    if "marketing" in role and ("not an engineer" in transcript or "mix those up" in transcript or "supposed to be leading" in transcript):
        return "Marketing Operations Leader (Non-Technical Persona)"
        
    pain = str(slots_data.get('Pain', '')).lower()
    rc = str(slots_data.get('RootCauses', '')).lower()
    
    if "unknown" in pain and "unknown" in rc:
        return "Unknown"
        
    combined = (pain + " " + rc + " " + role + " " + transcript).lower()
    if any(kw in combined for kw in ['as/400', 'mainframe', 'throttled', 'anchor', 'architecture', 'corporate it', 'governance']):
        return "Enterprise Architecture / IT Governance"
    if any(kw in combined for kw in ['renewal', 'revenue', 'board', 'forecast', 'pipeline', 'churn', 'sales', 'budget', 'marketing', 'campaign', 'attribution', 'convert']):
        return "Commercial / Marketing-oriented"
    return "Standard"

def classify_technology_profile(slots_data):
    tech_str = str(slots_data.get('Tech', '')).lower()
    if tech_str == "unknown" or not tech_str.strip():
        return "Unknown"
        
    limits_str = str(slots_data.get('Limits', '')).lower()
    combined_tech = tech_str + " " + limits_str
    
    if "as/400" in combined_tech or ("mainframe" in combined_tech and "snowflake" in combined_tech):
        return "Hybrid Enterprise Stack (Legacy Mainframe + Cloud Native)"
    
    has_modern = any(m in combined_tech for m in ['hubspot', 'saas', 'slack', 'sheets', 'cloud', 'mailchimp', 'monday.com', 'snowflake', 'dbt', 'aws', 'python'])
    has_legacy = any(l in combined_tech for l in ['postgresql', 'access', 'legacy', 'database', 'as/400', 'mainframe'])
    
    if has_modern and has_legacy:
        return "Hybrid Stack – Modern SaaS with Legacy Database dependency"
    elif has_modern:
        return "Modern SaaS Stack"
    elif has_legacy:
        return "Legacy Infrastructure Stack"
    return "Unknown"

def infer_transformation_strategy(slots_data):
    tech_str = str(slots_data.get('Tech', '')).lower()
    pain_str = str(slots_data.get('Pain', '')).lower()
    role_str = str(slots_data.get('Role', '')).lower()
    
    if "marketing" in role_str or "open rates" in pain_str or "convert" in pain_str:
        return "Marketing Performance Reconciliation"
    if tech_str == "unknown" and pain_str == "unknown":
        return "Discovery & Architecture Mapping"
        
    combined = tech_str + " " + pain_str + " " + role_str
    if any(kw in combined for kw in ['as/400', 'mainframe', 'throttled', 'anchor', 'legacy backbone']):
        return "Incremental Enterprise Modernization"
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
        "Extract raw factual metrics matching keys. If parameters are vague or structural information is absent, write 'Unknown' explicitly.\n"
        "If technical jargon is present but unverified or accompanied by explicitly admitted confusion, flag it as 'Unknown' under Tech.\n"
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
                if val in ["", "None", "null", "undefined", "vague", "empty"]:
                    st.session_state.slots[key] = "Unknown"
                else:
                    st.session_state.slots[key] = val
                    
        incoming_tags = result.get("tags", {})
        for key in st.session_state.tags:
            if key in incoming_tags:
                val_tag = str(incoming_tags[key]).strip()
                if val_tag in ["", "null", "undefined", "none"]:
                    st.session_state.tags[key] = "Unknown"
                else:
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

# Dynamically compute metadata
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
            st.session_state.last_analyzed = manual_input
            st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            if st.session_state.stage == 4:
                st.session_state.step4_validated = True
            st.rerun()
        else:
            st.warning("Please type the prospect input before running analysis pipelines.")
            
    if st.session_state.last_analyzed:
        st.markdown(f"<div class='last-input-box'><b>Last Analyzed Input:</b> {st.session_state.last_analyzed}</div>", unsafe_allow_html=True)

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
                st.session_state.blueprint_generated = False
                st.session_state.step4_validated = False
                st.rerun()
    with nav_col2:
        if st.session_state.stage < 4:
            if st.button("➡️ Next Stage"):
                st.session_state.stage += 1
                st.session_state.blueprint_generated = False
                st.session_state.step4_validated = False
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Parameters (Slots)")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val != "Unknown" else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Decoupled Psychological Profiling")
    
    box_lens = "status-box-filled" if derived_lens != "Unknown" else "status-box-empty"
    st.markdown(f"<div class='{box_lens}'><b>Decision Filter (Lens):</b> {derived_lens}</div>", unsafe_allow_html=True)
    
    box_tech = "status-box-filled" if derived_tech_profile != "Unknown" else "status-box-empty"
    st.markdown(f"<div class='{box_tech}'><b>Tech Profile:</b> {derived_tech_profile}</div>", unsafe_allow_html=True)
    
    for tag_name, label in [("Fear", "Identified Core Fear"), ("Verbatims", "Voice/Verbatim Mirror")]:
        tag_val = st.session_state.tags.get(tag_name, 'Unknown')
        b_class = "status-box-filled" if tag_val not in ["Unknown", "None"] else "status-box-empty"
        st.markdown(f"<div class='{b_class}'><b>{label}:</b> {tag_val}</div>", unsafe_allow_html=True)

# HIGH SECURITY BLOCKING GATE ON STEP 4 (CONFIDENCE SCORE METRIC BASED)
if st.session_state.stage == 4:
    st.markdown("---")
    st.subheader("🛡️ Strategic Gatekeeper Blueprint Compilation Control")
    
    # 1. Dynamic confidence calculations per discovery parameter
    slot_scores = {}
    slot_scores['Role'] = 1.0 if st.session_state.slots['Role'] != "Unknown" else 0.0
    slot_scores['Pain'] = 1.0 if st.session_state.slots['Pain'] != "Unknown" else 0.0
    
    # Tech: Successfully identifying an unverified tech posture grants maximum points
    tech_val = st.session_state.slots['Tech']
    if "Non-Technical Persona" in derived_lens and tech_val == "Unknown":
        slot_scores['Tech'] = 1.0  # Successfully Invalidated Jargon = High Value Strategic Discovery Insight
    elif tech_val != "Unknown":
        slot_scores['Tech'] = 1.0
    else:
        slot_scores['Tech'] = 0.0
        
    slot_scores['CompanySize'] = 1.0 if st.session_state.slots['CompanySize'] != "Unknown" else 0.0

    # 2. Global discovery matrix confidence aggregation
    total_confidence = sum(slot_scores.values()) / len(slot_scores)
    st.markdown(f"**Current Discovery Confidence Score:** `{total_confidence:.2f}` / `1.00` (Minimum Gatekeeper Validation Threshold: `0.70`)")
    
    # 3. Validation execution gate
    if total_confidence < 0.70:
        st.markdown(f"""
        <div class="lock-box">
            <h4>🔒 Blueprint Locked</h4>
            <p><b>Insufficient operational evidence to generate a strategic blueprint.</b></p>
            <p>Confidence Score: {total_confidence:.2f} (Required: 0.70). The framework prevents generation to protect diagnostic integrity.</p>
            <ul>
                <li>Role Data Status: {"✅ Verified" if slot_scores['Role'] == 1.0 else "❌ Missing"}</li>
                <li>Pain Data Status: {"✅ Verified" if slot_scores['Pain'] == 1.0 else "❌ Missing"}</li>
                <li>Tech Stack Status: {"⚠️ Explicitly Invalidated (Valid Discovery Insight)" if ("Non-Technical" in derived_lens and tech_val == "Unknown") else ("✅ Verified" if slot_scores['Tech'] == 1.0 else "❌ Missing")}</li>
                <li>Company Scale Status: {"✅ Verified" if slot_scores['CompanySize'] == 1.0 else "❌ Missing"}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.session_state.blueprint_generated = False
    else:
        st.success("✅ Strategic Gatekeeper Validation Passed. Structural profile integrity confirmed.")
        if st.session_state.step4_validated:
            if st.button("🎯 Compile Custom Strategic Blueprint", type="primary", use_container_width=True):
                st.session_state.blueprint_generated = True
                st.rerun()

    if st.session_state.blueprint_generated and total_confidence >= 0.70 and st.session_state.step4_validated:
        st.header(f"📋 Comprehensive Strategic Blueprint — [Strategy: {derived_strategy}]")
        
        with st.spinner("Compiling mirrored architecture diagnostic documentation..."):
            prompt_final = f"""
            Act as an elite B2B Enterprise Architecture Consultant and Management Psychologist.
            Generate a custom corporate strategic architecture report based EXCLUSIVELY on the provided metrics.
            
            [STRICT PROHIBITIONS]
            - NEVER use the word 'migration' or imply an infrastructure replacement. Use terms like 'phased coexistence' or 'progressive interoperability'.
            - NEVER propose 'data virtualization' or specific unmentioned infrastructure architectures. Use target terms like 'introducing integration layers between legacy and cloud-native workloads' or 'improving interoperability'.
            - DO NOT mention marketing tools (Mailchimp, Google Analytics, spreadsheets) unless they are explicitly present in the input parameters.

            ### METRICS FROM TRANSCRIPT:
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

            [GENERATION STRUCTURE]
            Write the report using clear business headers targeted to a decision maker. Use these exact titles for the strategic pillars:
               - Revenue Protection Strategy
               - Core Architectural Principles
               - Ecosystem Integration Priorities
            
            Under 'Revenue Protection Strategy', explain how architectural throttling and structural friction between systems directly impact operational business throughput and hidden organizational costs.
            """
            
            try:
                final_diag = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_final}],
                    temperature=0.0
                ).choices[0].message.content

                risk_level = "MEDIUM" if "Marketing" in derived_strategy else "MEDIUM-HIGH"
                
                if "Modernization" in derived_strategy or "Architecture" in derived_strategy:
                    directive_text = (
                        "Introduce integrated, non-intrusive layers between legacy and cloud-native workloads to improve interoperability. "
                        "Safeguard localized agility while establishing phased coexistence pathways acceptable to central IT governance."
                    )
                else:
                    directive_text = (
                        "Reconcile tracking methodologies and execute strict pipeline deduplication templates. "
                        "Eliminate infrastructure overhauls; fix human reporting alignment and analytical consistency."
                    )

                st.markdown(f"""
                <div class="recommendation-box">
                    <div class="priority-badge-high">⚠️ ADAPTIVE RISK LEVEL: {risk_level}</div>
                    <div style="font-size: 0.9em; margin-top: -10px; color: #FFD2D2;">
                        <b>Human & Corporate Posture Risk Assessment:</b><br>
                        • <b>Strategic Path:</b> Determined as <b>{derived_strategy}</b>.<br>
                        • <b>Ecosystem Directive:</b> {directive_text}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(final_diag)
            except Exception as e:
                st.error(f"Error compiling document asset: {e}")
