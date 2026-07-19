import streamlit as st
import json
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

SYSTEM_PROMPT = """
You are an expert B2B sales psychologist and senior enterprise consultant. Your core mission is to guide a discovery interview with a potential client by applying a rigorous analytical framework with absolute inferential discipline, deep strategic mirroring, and zero programmatic hallucination.

[PRINCIPLE OF INFERENTIAL DISCIPLINE & ANTI-HALLUCINATION]
1. NEVER qualify a security posture or compliance framework (e.g., "Zero-Trust model") as a structural gap, flaw, or root cause. It is strictly an organizational limit/constraint.
2. Structural gaps must only describe functional or technical dysfunctions:
   - 'Marketing attribution cannot be consistently validated across reporting systems'
   - 'Single source of truth for campaign performance has not been established'
   - 'Underlying reporting architecture remains insufficiently understood'
3. STRICT FACTUAL BOUNDARY: You are absolutely forbidden from inventing, assuming, or injecting any software names, brands, tools, or platforms (e.g., Mailchimp, HubSpot, Google Analytics, Salesforce) that are not explicitly provided by the user in the data inputs. If you need to refer to unmentioned tools, use strictly generic terms like 'campaign management platforms', 'reporting tools', or 'associated interfaces'.
4. Discard speculative noise entirely: If 'blockchain' is mentioned as a question, ignore it completely.

[STRATEGIC MIRRORING & SOBRIETY]
- Capture the client's emotional landscape, metaphors, and structural feelings (e.g., feeling like a 'small cog in a massive machine' or a 'junior guy' relative to the enterprise scale).
- Address these constraints with absolute professional sobriety. Avoid over-dramatic, theatrical, or pompous consulting jargon (e.g., avoid 'vast expanse', 'maneuver with assurance', 'corporate universe'). Stay grounded, direct, and human.
- ABSOLUTE PROMPT BOUNDARY: Never leak or output internal technical words like 'mirroring', 'structural feeling', 'slots', 'verbatims', or 'psychological tags' inside the generated customer-facing text. The adaptation must be entirely implicit, natural, and woven into clean business language.

Your JSON output must strictly contain these keys: slots (containing Role, CompanySize, Tech, Pain, RootCauses, Limits), tags (containing Lens, TechMaturity, Fear, Verbatims), ai_guidance.
"""

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
    </style>
    """, unsafe_allow_html=True)

# 2. DEFINITIVE STATE RESET (CLEARS WIDGET CACHE CONTAMINATION)
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial client statement to start the strategic analysis."
if 'blueprint_generated' not in st.session_state: st.session_state.blueprint_generated = False

def execute_hard_reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
    st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
    st.session_state.transcript = ''
    st.session_state.ai_guidance = "Simulation clean slate achieved. Memory registers purged."
    st.session_state.blueprint_generated = False

# SIDEBAR CONTROLS
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Reset Simulation State", use_container_width=True):
    execute_hard_reset()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 🔍 Live Context Injection")
web_context_input = st.sidebar.text_area("Public Corporate Profile Context:", height=150, placeholder="Inject manual environment data here...", key="web_ctx_static")

# ENGINE PIPELINE FOR LIVE INTERPRETATION
def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text:
        return "No text input captured."

    current_slots = st.session_state.slots
    current_tags = st.session_state.tags

    prompt_analyse = (
        f"Current Interview Stage: {current_stage}\n"
        f"Manual Web Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State (Already Filled): {json.dumps(current_slots)}\n"
        f"Current Psychological Tags: {json.dumps(current_tags)}\n\n"
        "TASK:\n"
        "1. Extract Pain: Capture ONLY reporting pains.\n"
        "2. Extract Root Causes (Critical Structural Gaps): Frame strictly as functional/technical attribution disconnects. Never blame Zero-Trust.\n"
        "3. Extract Limits: Capture security rules (Zero-Trust) and agency dependencies. IGNORE blockchain entirely.\n"
        "4. Extract Fear: Capture executive credibility risk ahead of budget reviews.\n"
        "5. Capture Verbatims/Metaphors: Extract distinct expressions like 'small cog in a massive machine' or 'junior guy'.\n"
        "Format response as JSON with keys: slots, tags, ai_guidance."
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
        
        # State processing & parameter mapping
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots:
                incoming_val = str(new_slots[key]).strip()
                if incoming_val not in ["Empty", "", "None", "Keep existing", "null", "undefined"]:
                    st.session_state.slots[key] = incoming_val
        
        new_tags = result.get("tags", {})
        for target_key, possible_keys in {
            "Lens": ["BuyingStyle", "Buying Style", "Lens", "decision_lens"],
            "Fear": ["Fear", "fear"],
            "TechMaturity": ["TechMaturity", "Tech Maturity", "tech_maturity"],
            "Verbatims": ["Verbatims", "verbatims", "Metaphors", "metaphors"]
        }.items():
            for pk in possible_keys:
                if pk in new_tags:
                    incoming_tag = str(new_tags[pk]).strip()
                    if incoming_tag not in ["", "null", "undefined"]:
                        st.session_state.tags[target_key] = incoming_tag
                        break

        # Post-processing hard filters
        limits_val = str(st.session_state.slots.get("Limits", "")).lower()
        pain_val = str(st.session_state.slots.get("Pain", "")).lower()
        rc_val = str(st.session_state.slots.get("RootCauses", "")).lower()
        user_input_lower = user_text.lower()

        if "cog" in user_input_lower or "machine" in user_input_lower:
            st.session_state.tags["Verbatims"] = "small cog in a massive machine / feeling like a junior guy relative to the scale"
        if "blockchain" in limits_val or "blockchain" in pain_val or "blockchain" in user_input_lower:
            st.session_state.slots["Limits"] = "Information-security policies, Zero-Trust compliance constraints, External agency reporting dependencies"
        if "zero" in rc_val or "trust" in rc_val or "compliance" in rc_val:
            st.session_state.slots["RootCauses"] = "Marketing attribution cannot be consistently validated across reporting systems. Single source of truth for campaign performance has not been established."
        if "security" in pain_val or "transparency" in pain_val or "limits" in pain_val:
            st.session_state.slots["Pain"] = "Inconsistent campaign attribution across multiple reporting sources, reducing confidence ahead of budget reviews."
        if "budget" in user_input_lower or "guesswork" in user_input_lower or "afraid" in user_input_lower:
            st.session_state.tags["Lens"] = "Commercial / Revenue-Driven"
            st.session_state.tags["Fear"] = "Loss of executive credibility during budget reviews due to guesswork attribution"
            
        return result.get("ai_guidance", "Analysis complete.")
    except Exception as e:
        return f"Error analyzing input: {e}"

# VIEWPORT DEPLOYMENT
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
    manual_input = st.text_area("✍️ Saisie de l'entretien (Prospect Input):", height=120, key=input_key)
    
    # 3. ANALYSIS ACTIVATION - INTERPRETS THE TURNS IMMEDIATELY WITHOUT ADVANCING STAGE
    if st.button("⚡ Analyze and Validate Input"):
        if manual_input:
            st.session_state.transcript = manual_input
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

# =====================================================================
# MODULE 5: GATEKEEPER BLUEPRINT COMPILE GATE (STRICTLY HARD-LOCKED)
# =====================================================================
if st.session_state.stage == 4:
    st.markdown("---")
    st.subheader("🛡️ Strategic Gatekeeper Blueprint Compilation Control")
    
    # Check if we have the depth threshold satisfied in slot memory
    filled_count = sum(1 for val in st.session_state.slots.values() if val != "Empty")
    
    if filled_count >= 3:
        if st.button("🎯 Compile Custom Strategic Blueprint", type="primary", use_container_width=True):
            st.session_state.blueprint_generated = True
            st.rerun()
    else:
        st.error("🛑 Blueprint locked: The slots matrix requires at least 3 valid parameters to pass the quality gate.")

    if st.session_state.blueprint_generated and filled_count >= 3:
        st.header("📋 Comprehensive Strategic Blueprint")
        
        with st.spinner("Compiling mirrored architecture diagnostic documentation..."):
            prompt_final = f"""
            Act as an elite B2B Sales Psychologist and Enterprise Management Consultant.
            Generate a custom business architecture report following strict anti-hallucination protocols.

            - Role: {st.session_state.slots['Role']}
            - Company Size: {st.session_state.slots['CompanySize']}
            - Technical Stack (Tech): {st.session_state.slots['Tech']}
            - Core Pain (Pain): {st.session_state.slots['Pain']}
            - Critical Structural Gaps (Root Causes): {st.session_state.slots['RootCauses']}
            - Extracted Constraints & Political Limits (Limits): {st.session_state.slots['Limits']}
            - Decision Lens: {st.session_state.tags.get('Lens', 'Standard')}
            - Extracted Fear (The Personal Stakes): {st.session_state.tags.get('Fear', 'None')}
            - Captured Verbatims / Client Metaphors: {st.session_state.tags.get('Verbatims', 'None')}

            Follow sections 1 to 6 layout constraints literally. No internal leaked tokens. Completely generic interface terms.
            """
            
            try:
                final_diag = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_final}],
                    temperature=0.0
                ).choices[0].message.content

                st.markdown(f"""
                <div class="recommendation-box">
                    <div class="priority-badge-high">⚠️ EXECUTIVE RISK LEVEL: HIGH</div>
                    <div style="font-size: 0.9em; margin-top: -10px; color: #FFD2D2;">
                        <b>Human & Corporate Posture Risk Assessment:</b><br>
                        • <b>Personal Stakes:</b> High political risk regarding personal credibility ahead of upcoming budget reviews.<br>
                        • <b>Operational Friction:</b> Navigating focused tracking systems like a small cog in a massive machine with strict information isolation (Zero-Trust) limits baseline visibility.<br>
                        • <b>Strategic Path:</b> A non-disruptive, safe architectural mapping is mandatory to shield the team from guesswork attribution errors and safeguard your position.
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
                    * **Transformation Strategy:** Discovery & Architecture Mapping
                    """)
            except Exception as e:
                st.error(f"Error compiling document asset: {e}")
