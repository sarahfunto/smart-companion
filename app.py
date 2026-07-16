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
You are an expert B2B sales psychologist and senior enterprise consultant. Your core mission is to guide a discovery interview with a potential client by applying a rigorous analytical framework.

[PSYCHOLOGICAL PROFILING - STRICT EVIDENCE-ONLY MODEL]
Analyze the prospect's profile across two distinct operational axes based strictly on verified evidence. Do NOT assume, extrapolate, or reuse old biases:

1. Buying Style (Decision Lens):
   - Risk / Compliance-Locked: Convicted by security, legal audits, data privacy, governance, process compliance, and failure prevention. (Select this if the prospect emphasizes confidentiality, security rules, and governance constraints).
   - Strategic / Growth-Driven: Convicted by market share, business model scalability, and long-term vision.
   - Standard: Default value if the client is highly evasive or data is insufficient to safely determine a lens. Do NOT default to Commercial.
   - Commercial / Revenue-Driven: ONLY if they explicitly talk about revenue, pipelines, sales, or renewals.

2. Tech Maturity: Assess the organizational complexity of their current tools. Formulate as a descriptive hybrid state (e.g., "Hybrid Stack - Mixed internal and third-party managed tools with varying ages").

[CRITICAL EXTRACTION & PIPELINE COHERENCE]
- 'companysize': Extract qualitative context if they refuse to give numbers (e.g., 'Not explicitly defined; requires more context').

- 'Tech': STRICT EXTRACTION RULE. Do NOT leave this slot 'Empty' if the client mentions functional components (databases, integrations, reporting systems, communication tools), even if they refuse to name specific vendors due to security. Extract these functional terms anonymously (e.g., 'Internal databases, reporting systems & communication integrations').

- 'Pain': Extract their state of diagnostic avoidance or operational inertia if they claim there is no specific pain point (e.g., 'Operational transparency and disclosure limits'). Do NOT invent clinical pain.

- 'Fear': STRICT NO-EXTRAPOLATION RULE. Identify high-stakes human and professional liabilities. If none are explicitly stated or if the client actively avoids sharing concerns, you MUST output 'Not yet confirmed' or 'None'. Do NOT label their non-disclosure/security constraints as a "fear" or "blind spot".

- OPERATIONAL DIAGNOSIS STRUCTURING:
  * Pain: Active business/operational consequences.
  * Root Causes: Technical reasons behind the pain. If unknown due to security, write strictly: "Not yet confirmed".
  * Limits (Constraints): Security or organizational barriers (e.g., 'Information-security rules prevent naming systems').

Your JSON output must strictly contain these keys: Role, CompanySize, Tech, Pain, RootCauses, Limits, BuyingStyle, TechMaturity, Fear...
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
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'None', 'TechMaturity': 'Standard'}
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
    placeholder="Example: Microsoft Corp. Experiencing reporting bottlenecks..."
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
        "1. Analyze the input. If they withhold vendors, extract functional anonymous terms ('databases, reporting tools') into 'Tech'.\n"
        "2. If they avoid sharing pain points, log this in 'Pain' as 'Operational transparency and disclosure limits'. Do not assume sales/revenue pains.\n"
        "3. Set 'Fear' strictly to 'Not yet confirmed' or 'None' if no explicit personal/corporate anxiety is stated. Do NOT invent 'blind spots'.\n"
        "4. Determine Decision Lens carefully. If they focus on governance, secrets, or info-sec, map strictly to 'Risk / Compliance-Locked'. If unknown, use 'Standard' or 'Strategic'.\n"
        "5. Preserve previously extracted values. Do not empty them.\n\n"
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
            "TechMaturity": ["TechMaturity", "Tech Maturity", "tech_maturity"]
        }.items():
            for pk in possible_keys:
                if pk in new_tags:
                    incoming_tag = str(new_tags[pk]).strip()
                    if incoming_tag not in ["", "null", "undefined"]:
                        st.session_state.tags[target_key] = incoming_tag
                        break
            
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
            with st.spinner("Generating deep expert diagnostic reflecting business outcomes..."):
                
                root_cause_val = st.session_state.slots.get('RootCauses', 'Not yet confirmed')
                is_unconfirmed = "not yet confirmed" in root_cause_val.lower() or "discovery" in root_cause_val.lower()
                
                risk_level = "MEDIUM" if is_unconfirmed else "HIGH"
                badge_class = "priority-badge-medium" if is_unconfirmed else "priority-badge-high"
                
                prompt_final = f"""
                Act as an elite, high-level B2B Sales and Management Consultant (McKinsey, Bain, BCG standard). 
                Analyze this profile STRICTLY using the provided parameters. Do NOT assume, extrapolate, or invent details:
                
                - Role: {st.session_state.slots['Role']}
                - Exact Company Size: {st.session_state.slots['CompanySize']}
                - Technical Stack (Tech): {st.session_state.slots['Tech']}
                - Core Pain (Pain): {st.session_state.slots['Pain']}
                - Critical Structural Gaps (Root Causes): {root_cause_val}
                - Extracted Constraints & Political Limits (Limits): {st.session_state.slots['Limits']}
                - Decision Lens: {st.session_state.tags.get('Lens', 'Standard')}
                - Extracted Fear: {st.session_state.tags.get('Fear', 'None')}
                - Tech Maturity State: {st.session_state.tags.get('TechMaturity', 'Standard')}

                CRITICAL STRUCTURAL RULES (PRUDENCE & INTELLECTUAL HONESTY):
                1. NO INVENTED TECH OR BRANDS: Do NOT use software names (HubSpot, Salesforce, PostgreSQL) unless explicitly written in 'Tech'. Speak strictly of "existing systems", "reporting assets" or "databases" as anonymized.
                2. NO SALES OR REVENUE HALLUCINATIONS: If 'Pain' or 'Fear' do NOT explicitly mention "sales", "revenue", "churn", or "customers", you are STRICTLY FORBIDDEN from writing these words or referencing commercial growth.
                3. PRUDENT CAUSALITY CHAIN: If the Root Cause is unconfirmed, write: "Current operational visibility is insufficient to confirm the underlying causes." or "Limited information prevents confirmation of structural bottlenecks." Do not assume or invent operational patterns.
                4. REALISTIC RECOMMENDATIONS: Because details are restricted, do NOT recommend heavy, intrusive, or premature actions (e.g. "Initiate an internal audit", "Deploy anonymous role-based reporting", "Process redesign workshop", "Cross-department task force"). Only recommend light, safe, discovery-driven frameworks:
                   * Discovery workshop
                   * Architecture mapping
                   * Data-flow assessment
                   * Stakeholder interviews
                5. RECOMMENDED STRATEGY: This must strictly be "Discovery & Architecture Mapping" under these circumstances.
                6. CORE FEAR TREATMENT: If 'Fear' is 'None' or 'Not yet confirmed', write exactly "Not yet confirmed" or "Insufficient information to determine executive concerns". Do not deduce fear from limits.

                Generate your report strictly following this layout:
                - Section 1: Strategic DNA Matrix (strictly display the extracted values).
                - Section 2: Strategic Causality Chain (use simple vertical arrow blocks showing Fear -> Root Cause -> Operational Pain -> Recommended Strategy).
                - Section 3: Executive Blueprint Narrative (calm, risk-aware, zero hype).
                - Section 4: Executive Recommendation callout box (emphasizing starting with a structured discovery phase before defining any roadmap).
                - Section 5: Expected Business Impact (highly aligned with mapping and verification).
                - Section 6: Immediate Priorities (must strictly be: Map current systems, Validate integration points, Identify reporting dependencies, Confirm executive objectives).
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
                            <b>Current Posture Assessment:</b><br>
                            • Structural opacity and diagnostic limit (strict security protocol)<br>
                            • Functional components are operational but unmapped<br>
                            • No immediate crisis reported; process validation required
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(final_diag)

                    if is_unconfirmed:
                        st.markdown(f"""
                        <div class="confidence-box">
                            <b>📋 Diagnostic Confidence: MEDIUM</b><br>
                            Operational constraints prevent total system evaluation. A non-disruptive discovery roadmap is mandatory before outlining structural recommendations.
                        </div>
                        """, unsafe_allow_html=True)

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
                        * **Business Risk:** {"🟡 **MEDIUM**" if is_unconfirmed else "🔴 **HIGH**"}
                        * **Transformation Strategy:** {"Discovery & Architecture Mapping" if is_unconfirmed else "Lightweight secure integration"}
                        """)

                except Exception as e:
                    st.error(f"Error generating blueprint: {e}")
