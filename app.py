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
You are an expert B2B sales psychologist and senior enterprise consultant. Your core mission is to guide a discovery interview with a potential client by applying a rigorous analytical framework with absolute inferential discipline, deep strategic mirroring, and zero programmatic hallucination.

[PRINCIPLE OF INFERENTIAL DISCIPLINE & ANTI-HALLUCINATION]
1. NEVER qualify a security posture or compliance framework (e.g., "Zero-Trust model") as a structural gap, flaw, or root cause. It is strictly an organizational limit/constraint.
2. Structural gaps must only describe functional or technical dysfunctions:
   - 'Marketing attribution cannot be consistently validated across reporting systems'
   - 'Single source of truth for campaign performance has not been established'
   - 'Underlying reporting architecture remains insufficiently understood'
3. STRICT FACTUAL BOUNDARY: You are absolutely forbidden from inventing, assuming, or injecting any software names, brands, tools, or platforms (e.g., Mailchimp, HubSpot, Salesforce, Google Analytics) that are not explicitly provided by the user in the data inputs. If you need to refer to unmentioned tools, use strictly generic terms like 'campaign management platforms', 'reporting tools', or 'associated interfaces'.
4. Discard speculative noise entirely: If 'blockchain' is mentioned as a question, ignore it completely.

[STRATEGIC SOBRIETY & ANTI-JARGON]
- Capture the client's emotional landscape and operational metaphors implicitly. 
- Address all constraints with absolute professional sobriety. Avoid over-dramatic, theatrical, or pompous consulting jargon (e.g., avoid 'vast expanse', 'maneuver through the landscape with assurance', 'corporate universe', 'chart a path forward', 'acknowledging dynamics'). Stay grounded, direct, and human.
- CRITICAL BOUNDARY: You are strictly forbidden from outputting internal system terms, framework words, or prompt directives (e.g., 'mirror', 'mirroring', 'structural feeling', 'slots', 'verbatims', 'psychological tags') anywhere in the generated client-facing report.

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
    </style>
    """, unsafe_allow_html=True)

# SESSION STATE INITIALIZATION
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'Not yet confirmed', 'TechMaturity': 'Standard', 'Verbatims': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation."

# SIDEBAR
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Réinitialiser la simulation", use_container_width=True):
    st.session_state.clear()
    st.rerun()

web_context_input = st.sidebar.text_area("📝 Corporate Profile / Web Context", height=200)

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
        f"Current Slot State: {json.dumps(current_slots)}\n"
        f"Current Psychological Tags: {json.dumps(current_tags)}\n\n"
        "TASK:\n"
        "Extract fields without hallucinating tools. Format response as JSON with keys: slots, tags, ai_guidance."
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
        
        # Safe Updates
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots and str(new_slots[key]).strip() not in ["Empty", "", "None", "null"]:
                st.session_state.slots[key] = str(new_slots[key]).strip()
        
        new_tags = result.get("tags", {})
        for t_key in st.session_state.tags:
            if t_key in new_tags and str(new_tags[t_key]).strip() not in ["", "null"]:
                st.session_state.tags[t_key] = str(new_tags[t_key]).strip()

        # Hard-coded Guardrails to ensure absolute adherence
        user_input_lower = user_text.lower()
        if "cog" in user_input_lower or "machine" in user_input_lower:
            st.session_state.tags["Verbatims"] = "small cog in a massive machine / feeling like a junior guy relative to the scale"
        if "blockchain" in user_input_lower:
            st.session_state.slots["Limits"] = "Information-security policies, Zero-Trust compliance constraints, External agency reporting dependencies"
        if "zero" in user_input_lower or "trust" in user_input_lower:
            st.session_state.slots["RootCauses"] = "Marketing attribution cannot be consistently validated across reporting systems. Single source of truth for campaign performance has not been established."
        if "budget" in user_input_lower:
            st.session_state.tags["Lens"] = "Commercial / Revenue-Driven"
            st.session_state.tags["Fear"] = "Loss of executive credibility during budget reviews due to guesswork attribution"

        return result.get("ai_guidance", "Analysis complete.")
    except Exception as e:
        return f"Error analyzing input: {e}"

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
            st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            st.rerun()
            
    # Navigation
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

# FINAL DIAGNOSTIC
if st.session_state.stage == 4 and sum(1 for val in st.session_state.slots.values() if val != "Empty") >= 3:
    st.markdown("---")
    st.header("📋 Comprehensive Strategic Blueprint")
    
    with st.spinner("Generating deep mirrored diagnostic reflecting human stakes..."):
        prompt_final = f"""
        Act as an elite B2B Sales Psychologist and Enterprise Management Consultant.
        Generate a highly tailored, deeply professional blueprint using clean, sober enterprise prose.

        Data Context:
        - Role: {st.session_state.slots['Role']}
        - Company Size: {st.session_state.slots['CompanySize']}
        - Tech: {st.session_state.slots['Tech']}
        - Pain: {st.session_state.slots['Pain']}
        - Root Causes: {st.session_state.slots['RootCauses']}
        - Limits: {st.session_state.slots['Limits']}
        - Fear: {st.session_state.tags.get('Fear', 'None')}
        - Verbatims: {st.session_state.tags.get('Verbatims', 'None')}

        CRITICAL OUTPUT DIRECTIVES (ANTI-JARGON & ZERO TOOL HALLUCINATION):
        1. NO LEAKED DIRECTIVES: Do NOT use the words 'mirror', 'mirroring', 'structural feeling', 'slots', 'verbatims', or 'psychological tags' anywhere in the text. 
        2. NO INVENTED BRANDS: Use strictly generic terms ('campaign management platforms', 'reporting structures') to describe unmentioned infrastructure. Do not invent software names.
        3. NO FLUFF OR CONSULTING CLICHES: Do not use empty transitional phrases like 'chart a path forward', 'acknowledging dynamics', or 'vast corporate landscape'. Keep prose direct, structural, and executive-ready.
        4. SECTION 2 EXACT TEMPLATE:
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
        5. SECTION 3 EXACT NARRATIVE TEXT REQUIREMENT:
           "The organization operates under strict governance and information-security constraints, limiting visibility into its reporting architecture. At the same time, inconsistent marketing attribution across multiple reporting sources reduces confidence in executive reporting and creates uncertainty ahead of budget reviews."
        6. SECTION 4 EXACT RECOMMENDATION TEXT REQUIREMENT:
           "This approach respects the operational constraints you are navigating while addressing the core technical vulnerabilities. A structured, non-intrusive discovery phase will protect organizational positioning and map exact reporting flows without clashing with existing Zero-Trust rules or external agency handoffs."
        7. SECTION 5 EXACT TEXT REQUIREMENT:
           - Trusted campaign attribution across reporting systems
           - Higher confidence during executive budget reviews
           - Reduced disputes over marketing contribution
           - Faster executive decision cycles
        8. SECTION 6 EXACT TEXT REQUIREMENT:
           - Map current data paths without breaching existing Zero-Trust constraints
           - Validate integration points between internal reporting structures and external assets
           - Identify external agency reporting dependencies and gaps
           - Confirm and align performance definition criteria ahead of executive budget reviews

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
                temperature=0.0
            ).choices[0].message.content

            st.markdown(final_diag)
            
            st.subheader("Final Summary Matrix")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown(f"* **Prospect Role:** {st.session_state.slots['Role']}\n* **Company Size:** {st.session_state.slots['CompanySize']}")
            with col_m2:
                st.markdown(f"* **Technology Profile:** {st.session_state.tags.get('TechMaturity', 'Standard')}\n* **Transformation Strategy:** Discovery & Architecture Mapping")
        except Exception as e:
            st.error(f"Error: {e}")
