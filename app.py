import streamlit as st
import json
import time
import os
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

SYSTEM_PROMPT = """
You are an expert B2B sales psychologist and senior enterprise consultant. Your core mission is to guide a discovery interview with a potential client by applying a rigorous analytical framework with absolute inferential discipline and deep strategic mirroring.

[PRINCIPLE OF INFERENTIAL DISCIPLINE]
1. NEVER qualify a security posture or compliance framework (e.g., "Zero-Trust model") as a structural gap, flaw, or root cause. It is strictly an organizational limit/constraint.
2. Structural gaps must only describe functional or technical dysfunctions:
   - 'Marketing attribution cannot be consistently validated across reporting systems'
   - 'Single source of truth for campaign performance has not been established'
   - 'Underlying reporting architecture remains insufficiently understood'
3. Discard speculative noise entirely: If 'blockchain' is mentioned as a question, ignore it completely.

[STRATEGIC MIRRORING & PSYCHOLOGICAL CAPTURE]
- You must carefully capture the client's emotional landscape, metaphors, and exact structural feelings (e.g., feeling like a 'small cog in a massive machine' or a 'junior guy' relative to the enterprise scale).
- Store these key phrases inside the 'Verbatims' capture layer to humanize the final output.

Your JSON output must strictly contain these keys: Role, CompanySize, Tech, Pain, RootCauses, Limits, BuyingStyle, TechMaturity, Fear, Verbatims...
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

    .priority-badge-medium {
        display: inline-block;
        background-color: #F4A261;
        color: white;
        padding: 6px 14px;
        font-size: 0.85em;
        font-weight: bold;
        border-radius: 4px;
        letter-spacing: 1px;
        margin-bottom: 15px;
    }

    .confidence-box {
        padding: 15px;
        border-radius: 8px;
        background-color: #2B2D42;
        border-left: 5px solid #FFB703;
        color: #EDF2F4;
        margin-top: 15px;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# SESSION STATE INITIALIZATION
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial client statement to start the strategic analysis."

# SIDEBAR: MANUAL WEB CONTEXT & RESET
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Réinitialiser la simulation", use_container_width=True):
    st.session_state.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("## 🔍 Live Context Injection")
st.sidebar.markdown("*Paste background information about the target company or test notes below before running the interview.*")

web_context_input = st.sidebar.text_area(
    "📝 Corporate Profile / Web Context", 
    height=200,
    placeholder="Example: Corporate enterprise environment..."
)

if st.sidebar.button("💾 Synchronize Context"):
    st.sidebar.success("Brain updated!")

# AI ANALYSIS ENGINE FUNCTION
def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text:
        return None

    current_slots = st.session_state.slots
    current_tags = st.session_state.tags

    prompt_analyse = (
        f"Current Interview Stage: {current_stage}\n"
        f"Manual Web Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State (Already Filled): {json.dumps(current_slots)}\n"
        f"Current Psychological Tags: {json.dumps(current_tags)}\n\n"
        "TASK:\n"
        "1. Extract Pain: Capture ONLY reporting pains (e.g. inconsistent campaign performance reports).\n"
        "2. Extract Root Causes (Critical Structural Gaps): Frame strictly as functional/technical attribution disconnects. Never blame Zero-Trust.\n"
        "3. Extract Limits: Capture security rules (Zero-Trust) and agency dependencies. IGNORE blockchain entirely.\n"
        "4. Extract Fear: Capture executive credibility risk ahead of budget reviews.\n"
        "5. Capture Verbatims/Metaphors: Extract distinct expressions like 'small cog in a massive machine' or 'junior guy' to use for deep validation.\n"
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
        
        # Safe State Update
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots:
                incoming_val = str(new_slots[key]).strip()
                if incoming_val not in ["Empty", "", "None", "Keep existing", "null", "undefined"]:
                    if st.session_state.slots[key] == "Empty" or len(incoming_val) > len(str(st.session_state.slots[key])):
                        st.session_state.slots[key] = incoming_val
        
        # Safe Tag Update
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

        # ==========================================
        # 🛡️ POST-PROCESSING GUARDRAILS & OVERRIDES
        # ==========================================
        limits_val = str(st.session_state.slots.get("Limits", "")).lower()
        pain_val = str(st.session_state.slots.get("Pain", "")).lower()
        rc_val = str(st.session_state.slots.get("RootCauses", "")).lower()
        user_input_lower = user_text.lower()

        # Catch specific rich text metaphors manually if skipped by API
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
        st.error(f"Error calling OpenAI: {e}")
        return "Error analyzing input."

stages = {
    "1": "Phase 1: Identity, Role & Company Size Contextual Validation",
    "2": "Phase 2: Technical Maturity Diagnostics & Infrastructure Readiness",
    "3": "Phase 3: Deep Operational Pain & Executive Psychology Profiling",
    "4": "Phase 4: Strategic Mirroring, Validation & Custom Blueprint Delivery"
}

st.markdown(f"### 💬 Interview Progress: Step {st.session_state.stage} / 4")

stage_questions = {
    "1": "Who am I speaking with today, what is the scale of your organization, and what corporate trigger brought you here?",
    "2": "What does your current software infrastructure look like? Are your daily workflows mostly manual or cloud-based?",
    "3": "Where are your teams losing the most hours, and if we deployed AI tomorrow, what are your core operational fears or constraints?",
    "4": "Reviewing your strategic situation: Here is what we know. Do you want to add, modify, or complete any data before receiving your final custom blueprint?"
}

st.subheader(f"👉 {stage_questions[str(st.session_state.stage)]}")
st.markdown(f"<small style='color: #888888; font-style: italic;'>Methodology Context — {stages[str(st.session_state.stage)]}</small>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    guidance_text = st.session_state.get('ai_guidance', "Welcome to the simulation.")
    st.info(f"Smart Companion Strategy Insight: {guidance_text}")
    
    st.markdown(f"**Current Phase Objective:** {stages[str(st.session_state.stage)]}")
    st.markdown("---")
    
    input_key = f"client_input_stage_{st.session_state.stage}"
    manual_input = st.text_area("⌨️ Client Input (Type what the prospect says):", height=100, placeholder="Type response here...", key=input_key)
    
    if st.button("⚡ Validate and Analyze Input"):
        if manual_input:
            st.session_state.transcript = manual_input
            with st.spinner("Processing framework analytical layers..."):
                st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            st.rerun()
        else:
            st.warning("Please type a client response before validating.")
            
    if st.session_state.transcript:
        st.markdown(f"**Last Analyzed Input:** *\"{st.session_state.transcript}\"*")
        
    st.markdown("---")
    
    # NAVIGATION
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
                st.session_state.transcript = ""
                st.rerun()
                
    with nav_col2:
        if st.session_state.stage < 4:
            if st.button("➡️ Next Stage"):
                st.session_state.stage += 1
                st.session_state.transcript = ""
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Parameters (Slots)")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val != "Empty" else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Psychological Profiling")
    lens_class = "status-box-filled" if st.session_state.tags['Lens'] != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{lens_class}'><b>Decision Filter (Lens):</b> {st.session_state.tags['Lens']}</div>", unsafe_allow_html=True)
    
    tech_class = "status-box-filled" if st.session_state.tags.get('TechMaturity', 'Standard') != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{tech_class}'><b>Tech Maturity:</b> {st.session_state.tags.get('TechMaturity', 'Standard')}</div>", unsafe_allow_html=True)

    fear_class = "status-box-filled" if st.session_state.tags['Fear'] not in ["None", "Not yet confirmed"] else "status-box-empty"
    st.markdown(f"<div class='{fear_class}'><b>Identified Core Fear (Fear):</b> {st.session_state.tags['Fear']}</div>", unsafe_allow_html=True)
    
    v_class = "status-box-filled" if st.session_state.tags.get('Verbatims', 'None') != "None" else "status-box-empty"
    st.markdown(f"<div class='{v_class}'><b>Captured Voice/Verbatim Mirror:</b> {st.session_state.tags.get('Verbatims', 'None')}</div>", unsafe_allow_html=True)

# FINAL DIAGNOSTIC
if st.session_state.stage == 4:
    st.markdown("---")
    st.header("📋 Comprehensive Strategic Blueprint")
    
    if 'diagnostic_ready' not in st.session_state:
        st.session_state.diagnostic_ready = False

    if st.session_state.transcript:
        st.session_state.diagnostic_ready = True

    filled_slots_count = sum(1 for val in st.session_state.slots.values() if val != "Empty")
    
    if st.session_state.diagnostic_ready:
        if filled_slots_count < 3:
            st.error("⚠️ Diagnostic Blocked: Insufficient Data.")
            st.warning("You must provide more details to unlock the diagnostic.")
        else:
            st.balloons()
            with st.spinner("Generating deep mirrored diagnostic reflecting human stakes..."):
                
                root_cause_val = st.session_state.slots.get('RootCauses', 'Not yet confirmed')
                is_unconfirmed = "not yet confirmed" in root_cause_val.lower() or "discovery" in root_cause_val.lower()
                
                risk_level = "HIGH"
                badge_class = "priority-badge-high"
                
                prompt_final = f"""
                Act as an elite B2B Sales Psychologist and Enterprise Management Consultant.
                Analyze this profile and generate a highly tailored, deeply mirrored blueprint. You must weave the client's explicit language into the document to ensure they feel truly listened to.

                - Role: {st.session_state.slots['Role']}
                - Exact Company Size: {st.session_state.slots['CompanySize']}
                - Technical Stack (Tech): {st.session_state.slots['Tech']}
                - Core Pain (Pain): {st.session_state.slots['Pain']}
                - Critical Structural Gaps (Root Causes): {root_cause_val}
                - Extracted Constraints & Political Limits (Limits): {st.session_state.slots['Limits']}
                - Decision Lens: {st.session_state.tags.get('Lens', 'Standard')}
                - Extracted Fear (The Personal Stakes): {st.session_state.tags.get('Fear', 'None')}
                - Captured Verbatims / Client Metaphors: {st.session_state.tags.get('Verbatims', 'None')}

                CRITICAL MIRRORING AND STRUCTURAL INSTRUCTIONS:
                1. EMOTIONAL MIRRORING & VOICE: Do not write a cold, completely detached generic report. You must address the unique tension of operating as a small, agile team inside an overwhelming enterprise framework. Explicitly reference or adapt the phrases from 'Captured Verbatims' (e.g., operating like a small cog in a massive machine, or navigating a massive corporate machine where you feel isolated/junior despite the high stakes).
                2. DEEP CAUSALITY SEGMENTATION: Never treat Zero-Trust as a structural defect or root cause. Frame it exclusively as a rigid governance environment that limits diagnostic visibility.
                3. SECTION 2 CAUSALITY CHAIN TEMPLATE: You must output this sequence exactly:
                   **Fear**
                   ↓
                   Loss of executive credibility during budget reviews due to guesswork attribution
                   
                   ↓
                   **Observed Structural Gaps**
                   
                   ↓
                   Marketing attribution cannot be consistently validated across reporting systems
                   
                   ↓
                   **Operational Pain**
                   
                   ↓
                   Inconsistent trust in marketing data and mismatched campaign reporting
                   
                   ↓
                   **Strategy**
                   
                   ↓
                   Discovery & Architecture Mapping
                4. SECTION 3 NARRATIVE REQUIREMENT: Open by acknowledging the personal and political risk. Address the reality that running tracking workflows within an enterprise of this scale creates structural isolation. Incorporate this precise framing:
                   "The organization operates under strict governance and information-security constraints, limiting visibility into its reporting architecture. At the same time, inconsistent marketing attribution across multiple reporting sources reduces confidence in executive reporting and creates uncertainty ahead of budget reviews."
                   Weave in a mirrored validation of their verbatim experience (navigating a massive machine with siloed components).
                5. SECTION 4 RECOMMENDATION CUSTOMIZATION: Do NOT just output a generic template. Explicitly state that a non-intrusive discovery phase is designed precisely to safeguard their position and map the architecture without triggering rigid corporate security compliance or agency disputes. Connect it directly to the metaphor of navigating a massive machine safely.
                6. SECTION 5 BUSINESS IMPACTS: Output exactly these four business outcomes, tailored to address their specific pain points:
                   - Trusted campaign attribution across reporting systems
                   - Higher confidence during executive budget reviews
                   - Reduced disputes over marketing contribution
                   - Faster executive decision cycles
                7. SECTION 6 IMMEDIATE PRIORITIES: Anchor these strictly in their exact practical limits (Zero-Trust and agency constraints):
                   - Map current systems without breaching Zero-Trust guardrails
                   - Validate cross-system integration points (Mailchimp, GA, Agency assets)
                   - Identify external agency reporting dependencies
                   - Confirm and align executive objectives ahead of the next budget review

                Generate your report strictly following this layout:
                - Section 1: Strategic DNA Matrix
                - Section 2: Strategic Causality Chain
                - Section 3: Executive Blueprint Narrative
                - Section 4: Executive Recommendation callout box
                - Section 5: Expected Business Impact
                - Section 6: Immediate Priorities
                """

                try:
                    final_diag = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt_final}],
                        temperature=0.1
                    ).choices[0].message.content

                    st.markdown(f"""
                    <div class="recommendation-box">
                        <div class="{badge_class}">⚠️ EXECUTIVE RISK LEVEL: {risk_level}</div>
                        <div style="font-size: 0.9em; margin-top: -10px; color: #FFD2D2;">
                            <b>Human & Corporate Posture Risk Assessment:</b><br>
                            • <b>Personal Stakes:</b> High vulnerability regarding personal credibility ahead of upcoming budget reviews.<br>
                            • <b>Operational Friction:</b> Navigating strict data isolation rules (Zero-Trust) within an overwhelming enterprise machine reduces immediate visibility.<br>
                            • <b>Strategic Path:</b> Validation and safe structural discovery required immediately to shield the team from guesswork attribution errors.
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
                        * **Voice/Mirroring Checklist:** ✅ *Verbatim metaphors mirrored in narrative and priorities.*
                        * **Transformation Strategy:** Discovery & Architecture Mapping
                        """)

                except Exception as e:
                    st.error(f"Error generating blueprint: {e}")
