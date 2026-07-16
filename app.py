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

[PSYCHOLOGICAL PROFILING - MULTIDIMENSIONAL MODEL]
Instead of a single flat tag, you must analyze the prospect's profile across two distinct operational axes:

1. Buying Style (Decision Lens): This answers: "What argument will convince this person to sign?"
   - Commercial / Revenue-Driven: Convicted by renewal rates, forecasting confidence, pipeline speed, and sales team efficiency (e.g., VP of Sales, Chief Revenue Officer). Even if they mention technical databases, if their goal is revenue, they belong here.
   - Strategic / Growth-Driven: Convicted by market share, business model scalability, and long-term vision (e.g., CEO, Founders).
   - Risk / Compliance-Locked: Convicted by security, legal audits, data privacy, and failure prevention (e.g., CFO, Legal Counsel).
   - Technical / Architecture-Driven: ONLY for roles whose primary job is building and maintaining systems (CTO, Lead Architect) and who care about clean code, scalability, and stack modernism.

2. Tech Maturity: Assess the organizational complexity of their current tools. Do NOT output generic terms like 'Medium' or 'Low'. Instead, build a descriptive hybrid state representation:
   - Formulate as: "Hybrid Stack - Modern SaaS ([Modern Tools]) with Legacy Database ([Legacy Tools]) dependency" or "Modern Agile - SaaS Native with data pipeline gaps".

[CRITICAL EXTRACTION & PIPELINE COHERENCE]
- 'companysize': Must strictly reflect the prospect's employer scale (e.g., '11 employees').

- 'Fear': Identify raw, high-stakes human and professional liabilities expressed by the executive. Reject abstract concepts like "losing competitive advantage" or "falling behind modern expectations." Focus strictly on:
  * "Being surprised by a major renewal loss"
  * "Making strategic decisions based on unreliable forecasts"
  * "Losing executive or board confidence because pipeline data cannot be trusted"

- OPERATIONAL DIAGNOSIS STRUCTURING:
  * Pain: Strictly limit this to the active, business/operational consequences expressed (e.g., 'Unreliable sales forecasts for the board', 'Zero visibility into product adoption for renewal security'). This is the actual emotional and business pain.
  * Root Causes: The structural or technical reasons behind the Pain (e.g., 'Lack of data integration between PostgreSQL and HubSpot', 'Product data locked inside isolated databases').
  * Limits (Constraints): The human, organizational, or historical barriers that restrict possible solutions. 
    - CRITICAL: Founder resistance (e.g., 'Founder refuses to give up Microsoft Access'), explicit tool rejections (e.g., 'Salesforce abandoned as too heavy/complex'), and team constraints (e.g., 'Small sales team of 11 people') MUST be classified under 'Limits'. NEVER leave 'Limits' empty if such organizational barriers are mentioned.

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
        line-height: 1.6;
    }

    .dna-container {
        background-color: #1A1F26;
        border: 1px solid #2E6BFF;
        padding: 20px;
        margin-bottom: 25px;
        border-radius: 10px;
    }

    .causality-chain {
        background-color: #1E2329;
        border-left: 5px solid #E63946;
        padding: 15px;
        margin-bottom: 25px;
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)

# SESSION STATE INITIALIZATION
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'RootCauses': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'None', 'TechMaturity': 'Standard'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial client statement to start the strategic analysis."

stages = {
    "1": "Phase 1: Identity, Role & Company Size Contextual Validation",
    "2": "Phase 2: Technical Maturity Diagnostics & Infrastructure Readiness",
    "3": "Phase 3: Deep Operational Pain & Executive Psychology Profiling",
    "4": "Phase 4: Strategic Mirroring, Validation & Custom Blueprint Delivery"
}

# AI ANALYSIS ENGINE FUNCTION
def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text:
        return None

    current_slots = st.session_state.slots
    current_tags = st.session_state.tags

    prompt_analyse = (
        f"Current Interview Stage: {stages[str(current_stage)]}\n"
        f"Manual Web Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State (Already Filled): {json.dumps(current_slots)}\n"
        f"Current Psychological Tags: {json.dumps(current_tags)}\n\n"
        "TASK:\n"
        "1. Analyze the client's input. Identify technical facts AND emotional signals.\n"
        "2. Update the Slots and Psychological Tags. CRITICAL RULES:\n"
        "   - Parse Company Size (e.g., 'medium sized company', '10 employees') into 'CompanySize'.\n"
        "   - Parse the job title/function into 'Role'. Never mix them up.\n"
        "   - You MUST PRESERVE and carry forward all previously filled slots if they are not explicitly replaced. Do NOT overwrite existing data with 'Empty'.\n"
        "3. Formulate the next strategic recommendation for the consultant.\n\n"
        "Format your response STRICTLY as a JSON object with these exact keys:\n"
        "{\n"
        "  \"slots\": { \"Role\": \"...\", \"CompanySize\": \"...\", \"Tech\": \"...\", \"Pain\": \"...\", \"RootCauses\": \"...\", \"Limits\": \"...\" },\n"
        "  \"tags\": { \"Lens\": \"...\", \"Fear\": \"...\", \"TechMaturity\": \"...\" },\n"
        "  \"ai_guidance\": \"Provide tactical, emotionally aware guidance here.\"\n"
        "}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_analyse}
            ],
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots and new_slots[key] not in ["Empty", "", "None", "Keep existing or update"]:
                st.session_state.slots[key] = new_slots[key]
        
        new_tags = result.get("tags", {})
        for key in st.session_state.tags:
            if key in new_tags and new_tags[key] not in ["None", ""]:
                st.session_state.tags[key] = new_tags[key]
        
        current_role = str(st.session_state.slots.get("Role", "")).upper()
        non_tech_roles = ["SALES", "VP OF SALES", "VP SALES", "MARKETING", "CFO", "CEO", "FOUNDER", "DIRECTOR"]

        for tag_key in st.session_state.tags:
            if "DECISION" in tag_key.upper() or "LENS" in tag_key.upper() or "BUYINGSTYLE" in tag_key.upper():
                if any(role in current_role for role in non_tech_roles):
                    st.session_state.tags[tag_key] = "Commercial / Revenue-Driven"
                elif "CTO" in current_role or "ARCHITECT" in current_role or "DEVELOPER" in current_role:
                    st.session_state.tags[tag_key] = "Technical / Architecture-Driven"
            
        return result.get("ai_guidance", "Analysis complete.")
    except Exception as e:
        st.error(f"Error calling OpenAI: {e}")
        return "Error analyzing input."

st.title("🎙️ Smart Companion — Expert Workspace")

# SIDEBAR: MANUAL WEB CONTEXT INJECTION
st.sidebar.markdown("## 🔍 Live Context Injection")
st.sidebar.markdown("*Paste background information about the target company or test notes below before running the interview.*")

web_context_input = st.sidebar.text_area(
    "📝 Corporate Profile / Web Context", 
    height=200,
    placeholder="Example: Microsoft Corp. Experiencing significant reporting bottlenecks in mid-market auditing fields..."
)

if st.sidebar.button("💾 Synchronize Context"):
    st.sidebar.success("Brain updated with the latest background insights!")

# INTERVIEW STATE & QUESTIONS
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
    guidance_text = st.session_state.get('ai_guidance', "Welcome to the simulation. Input the initial client statement to start the strategic analysis.")
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
    
    # NAVIGATION SYSTEM
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

    fear_class = "status-box-filled" if st.session_state.tags['Fear'] != "None" else "status-box-empty"
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
                prompt_final = f"""
                Act as an elite, high-level B2B Sales and Management Consultant (McKinsey, Bain, BCG standard). Analyze this profile:
                - Role: {st.session_state.slots['Role']}
                - Exact company Size: {st.session_state.slots['CompanySize']}
                - Technical Stack: {st.session_state.slots['Tech']}
                - Core Pain: {st.session_state.slots['Pain']}
                - Critical Structural Gaps (Root Causes): {st.session_state.slots['RootCauses']}
                - Extracted Constraints & Political Limits: {st.session_state.slots['Limits']}
                - Decision Lens: {st.session_state.tags.get('Lens', 'Commercial / Executive')}
                - Extracted Fear: {st.session_state.tags.get('Fear', 'Being surprised by a major renewal loss')}
                - Tech Maturity State: {st.session_state.tags.get('TechMaturity', 'Hybrid Stack')}

                You must build a highly tailored, clinical, and high-impact Strategic Blueprint. Follow these instructions strictly to maintain a calm, highly objective, senior enterprise consultant tone:

                1. CRITICAL TONE ADJUSTMENT:
                   - NO marketing hype, overly dramatic words, or SaaS sales pitches. 
                   - Do NOT use phrases like "flirting with disaster", "cold, hard truth", "operational blindness", "becoming irrelevant", "unforgiving market", or "reducing your competitive advantage".
                   - Use calm, business-first risk-assessment statements:
                     * "increasing operational uncertainty and renewal risk"
                     * "weakening revenue predictability"
                     * "increasing business risk"
                     * "limited operational visibility"

                2. SECTION 1: STRATEGIC DNA MATRIX (MANDATORY FORMAT)
                   Render a clean, high-impact overview using the following structured fields. Rely strictly on the exact context and details gathered during the interview:
                   * **Strategic Business Objective**: Protect recurring revenue
                   * **Decision Lens**: {st.session_state.tags.get('Lens', 'Commercial / Revenue-Driven')}
                   * **Core Fear**: {st.session_state.tags.get('Fear', 'Being surprised by a major renewal loss')}
                   * **Operational Pain**: {st.session_state.slots['Pain']}
                   * **Root Cause**: {st.session_state.slots['RootCauses']}
                   * **Constraints**: {st.session_state.slots['Limits']}
                   * **Recommended Strategy**: Modernize and bridge existing assets through lightweight synchronization rather than costly, disruptive tool replacement.
                   * **Expected Business Outcomes**:
                     - Reliable revenue forecasting
                     - Early renewal risk detection
                     - Higher renewal confidence
                     - Improved customer retention

                3. SECTION 2: STRATEGIC CAUSALITY CHAIN (MANDATORY VISUAL FLOW)
                   Present the sequential mapping of the current operational friction using this precise flow (use markdown styling, bold headers, and exact arrow layout):
                   
                   **BUSINESS FEAR**
                   {st.session_state.tags.get('Fear', 'Being surprised by a major renewal loss')}
                   
                   ↓
                   
                   **ROOT CAUSE**
                   {st.session_state.slots['RootCauses']}
                   
                   ↓
                   
                   **OPERATIONAL PAIN**
                   {st.session_state.slots['Pain']}
                   
                   ↓
                   
                   **STRATEGIC RESPONSE**
                   Connect PostgreSQL product usage data with HubSpot while maintaining compatibility with Microsoft Access through a phased modernization strategy.

                4. SECTION 3: EXECUTIVE BLUEPRINT NARRATIVE:
                   * Paragraph 1 (The Core Paradox): "Your biggest challenge is not generating more pipeline—it is trusting the pipeline you already have." Explain clearly, without dramatic hyperbole, how disconnecting system data creates unnecessary uncertainty around forecasts and renewal cycles. Use terms like "increasing operational uncertainty and renewal risk" or "weakening revenue predictability."
                   * Paragraph 2 (Tactical Adaptation to Constraints): "Given your current constraints, the solution must adapt to your environment rather than force your organization to adapt to new technology." Advise against total migrations or heavy tool replacements (especially considering their specific constraints/team size of {st.session_state.slots['CompanySize']}). Propose a lightweight integration layer or middleware layer instead. DO NOT reference any specific third-party integration brands (like Zapier, Make, etc.) to keep the consulting strictly independent.
                   * End this section with the exact closing sentence: "The objective is not to replace your existing ecosystem, but to make it work as a unified decision-support platform."

                5. SECTION 4: EXPECTED BUSINESS IMPACT (MANDATORY MBB FORMAT)
                   Output a clean bulleted list detailing the exact strategic effects under the title "### 📈 Expected Business Impact":
                   - **Improved renewal visibility** across key accounts
                   - **Higher forecasting accuracy** for executive reporting
                   - **Faster identification** of churn risks
                   - **Better alignment** between Product and Sales
                   - **Increased confidence** in strategic planning

                6. SECTION 5: IMMEDIATE PRIORITIES (MANDATORY FORMAT)
                   Output a highly-structured numbered list under the title "### 🎯 Immediate Priorities" with these exact objectives:
                   * 1. **Establish the Data Bridge**: Connect PostgreSQL product usage data with HubSpot while maintaining compatibility with Microsoft Access through a phased modernization strategy, avoiding heavy platform migrations.
                   * 2. **Implement Account Health Scores**: Implement Account Health Scores based on product usage signals to identify renewal risks early.
                   * 3. **Standardize Forecasting Reviews**: Introduce recurring forecasting reviews based on unified operational data to restore executive and board confidence.
                """

                try:
                    final_diag = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt_final}]
                    ).choices[0].message.content

                    st.markdown(f"""
                    <div class="recommendation-box">
                        {final_diag}
                    </div>
                    """, unsafe_allow_html=True)

                    st.subheader("Final Summary Matrix")
                    st.write(f"• **Prospect Role:** {st.session_state.slots['Role']}")
                    st.write(f"• **Company Scale:** {st.session_state.slots['CompanySize']}")
                    st.write(f"• **Tech Maturity:** {st.session_state.tags.get('TechMaturity', 'Medium')}")
                    st.write(f"• **Decision Lens:** {st.session_state.tags.get('Lens', 'Commercial / Revenue-Driven')}")

                    st.markdown("---")
                    st.subheader("📊 Operational Diagnosis")

                    st.error(f"""**🔴 Core Business Pain:**  
{st.session_state.slots.get('Pain', 'Empty')}""")

                    st.warning(f"""**⚙️ Technical Root Causes:**  
{st.session_state.slots.get('RootCauses', 'Empty')}""")

                    st.info(f"""**⚠️ Constraints & Limits:**  
{st.session_state.slots.get('Limits', 'Empty')}""")

                except Exception as e:
                    st.error(f"Error generating blueprint: {e}")
