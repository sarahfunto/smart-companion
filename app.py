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

- OPERATIONAL DIAGNOSIS STRUCTURING (STRICTLY DISCONNECTED):
  * Pain: Strictly limit this to the active, business/operational consequences expressed (e.g., 'Unreliable executive reporting and operational forecasting').
  * Root Causes: The structural or technical reasons behind the Pain. 
    - CRITICAL: Do NOT copy communication constraints here. If the user refuses to share technical details (e.g., "I cannot disclose our systems due to info-sec"), the Root Cause MUST be categorized as "Not yet confirmed" or "Requires additional discovery".
  * Limits (Constraints): The human, organizational, communication, or historical barriers that restrict possible solutions or disclosure.
    - Information-security rules, NDAs, or "refusal to name vendors" MUST be classified under 'Limits', NEVER under 'Root Causes'.

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
        "   - If the prospect expresses that security rules prevent naming systems, classify this under 'Limits'. Set 'RootCauses' strictly to 'Not yet confirmed' or 'Requires additional discovery'.\n"
        "3. Formulate the next strategic recommendation for the consultant.\n\n"
        "Format your response STRICTLY as a JSON object with these exact keys:\n"
        "{\n"
        "  \"slots\": { \"Role\": \"...\", \"CompanySize\": \"...\", \"Tech\": \"...\", \"Pain\": \"...\", \"RootCauses\": \"...\", \"Limits\": \"...\" },\n"
        "  \"tags\": { \"BuyingStyle\": \"...\", \"Fear\": \"...\", \"TechMaturity\": \"...\" },\n"
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
        
        # Update Slots safely
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots and new_slots[key] not in ["Empty", "", "None", "Keep existing or update"]:
                st.session_state.slots[key] = new_slots[key]
        
        # Robust Tag mapping to align with state definitions
        new_tags = result.get("tags", {})
        for target_key, possible_keys in {
            "Lens": ["BuyingStyle", "Buying Style", "Lens", "decision_lens"],
            "Fear": ["Fear", "fear"],
            "TechMaturity": ["TechMaturity", "Tech Maturity", "tech_maturity"]
        }.items():
            for pk in possible_keys:
                if pk in new_tags and new_tags[pk] not in ["None", "", "Standard"]:
                    st.session_state.tags[target_key] = new_tags[pk]
                    break
        
        # Strategic fallback logic for Decision Lens based on Role keywords
        current_role = str(st.session_state.slots.get("Role", "")).upper()
        non_tech_roles = ["SALES", "VP", "MARKETING", "CFO", "CEO", "FOUNDER", "DIRECTOR", "EXECUTIVE", "PRESIDENT", "MANAGER"]

        if st.session_state.tags["Lens"] == "Standard":
            if any(role in current_role for role in non_tech_roles):
                st.session_state.tags["Lens"] = "Commercial / Revenue-Driven"
            elif any(tech_role in current_role for tech_role in ["CTO", "ARCHITECT", "DEVELOPER", "ENGINEER"]):
                st.session_state.tags["Lens"] = "Technical / Architecture-Driven"
            
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
                
                # Dynamic adjustment of the displayed slot value for UI/UX rendering
                mapped_pain = st.session_state.slots.get('Pain', '')
                if mapped_pain == "Empty" or "sales" in mapped_pain.lower() or "renewal" in mapped_pain.lower():
                    mapped_pain = "Unreliable executive reporting and operational forecasting"
                    st.session_state.slots['Pain'] = mapped_pain

                # Determine dynamic confidence and risk parameters
                root_cause_val = st.session_state.slots.get('RootCauses', 'Not yet confirmed')
                is_unconfirmed = "not yet confirmed" in root_cause_val.lower() or "discovery" in root_cause_val.lower() or "insufficient" in root_cause_val.lower()
                
                risk_level = "MEDIUM" if is_unconfirmed else "HIGH"
                badge_class = "priority-badge-medium" if is_unconfirmed else "priority-badge-high"
                
                prompt_final = f"""
                Act as an elite, high-level B2B Sales and Management Consultant (McKinsey, Bain, BCG standard). 
                Analyze this profile STRICTLY using the provided parameters. Do NOT assume, hallucinate, or carry over any external software systems, architectures, or business goals unless they are explicitly written below:
                
                - Role: {st.session_state.slots['Role']}
                - Exact Company Size: {st.session_state.slots['CompanySize']}
                - Technical Stack (Tech): {st.session_state.slots['Tech']}
                - Core Pain (Pain): {st.session_state.slots['Pain']}
                - Critical Structural Gaps (Root Causes): {root_cause_val}
                - Extracted Constraints & Political Limits (Limits): {st.session_state.slots['Limits']}
                - Decision Lens: {st.session_state.tags.get('Lens', 'Standard')}
                - Extracted Fear: {st.session_state.tags.get('Fear', 'None')}
                - Tech Maturity State: {st.session_state.tags.get('TechMaturity', 'Standard')}

                CRITICAL STABILITY RULES (PREVENT CONTAMINATION):
                1. STRICT TOOL BLOCK: If the Tech slot does not contain "HubSpot", "PostgreSQL", or "Microsoft Access", you are FORBIDDEN from naming them or hinting at them. Use generic terms instead like "existing business systems", "internal databases", "legacy tools", or "third-party platforms" as described by the prospect.
                2. STRICT TERMINOLOGY BLOCK: If the Pain or Fear slots do NOT explicitly mention words like "sales", "renewal", "product adoption", "churn", or "retention", do NOT use them. Adapt the business context entirely to the prospect's actual input (e.g., if they are in public service, healthcare, finance, or secure systems, focus purely on their described operational targets like "process reliability", "compliance verification", or "secure organizational reporting").
                3. NO INVENTED VENDORS: If the prospect stated they cannot name vendors due to info-sec rules, your entire diagnostic must refer to their stack anonymously as "protected infrastructure" or "internal business architectures".

                You must build a highly tailored, clinical, and high-impact Strategic Blueprint following this exact layout:

                1. CRITICAL TONE ADJUSTMENT:
                   - NO marketing hype or dramatic consulting clichés.
                   - Use calm, business-first risk-assessment statements: "increasing operational uncertainty", "weakening process predictability", "increasing operational risk", "limited process visibility".

                2. SECTION 1: STRATEGIC DNA MATRIX (MANDATORY FORMAT)
                   Render an overview strictly mapped to the provided slots:
                   * **Strategic Business Objective**: Improve strategic decision-making through reliable organizational reporting. (Or: Enhance decision quality through more reliable operational forecasting).
                   * **Decision Lens**: {st.session_state.tags.get('Lens', 'Standard')}
                   * **Core Fear**: {st.session_state.tags.get('Fear', 'None')}
                   * **Operational Pain**: {st.session_state.slots['Pain']}
                   * **Root Cause**: {root_cause_val}
                   * **Constraints**: {st.session_state.slots['Limits']}
                   * **Recommended Strategy**: {"Conduct a structured discovery phase to map infrastructure dependencies." if is_unconfirmed else "Modernize and secure existing assets through a lightweight integration layer rather than costly, disruptive platform replacement."}
                   * **Expected Business Outcomes**: [Identify 3 to 4 outcomes directly solving the 'Pain' and aligned with 'Decision Lens'. Do NOT reference renewals or sales unless explicitly supported.]

                3. SECTION 2: STRATEGIC CAUSALITY CHAIN (MANDATORY VISUAL FLOW)
                   Present the sequential mapping of the current operational friction using this precise flow (use markdown styling, bold headers, and exact arrow layout):
                   
                   **BUSINESS FEAR**
                   {st.session_state.tags.get('Fear', 'None')}
                   
                   ↓
                   
                   **ROOT CAUSE**
                   {root_cause_val}
                   
                   ↓
                   
                   **OPERATIONAL PAIN**
                   {st.session_state.slots['Pain']}
                   
                   ↓
                   
                   **STRATEGIC RESPONSE**
                   {"Initiate a dedicated technical discovery track to define current operational friction points safely." if is_unconfirmed else "[Write a 1-sentence strategic response strictly utilizing the 'Tech' slot data and 'Limits'. If tools are anonymous, use terms like 'securely connecting internal systems while respecting information-security constraints']"}

                4. SECTION 3: EXECUTIVE BLUEPRINT NARRATIVE:
                   * Paragraph 1 (The Core Paradox): Describe their challenge strictly based on their 'Pain' and 'Fear'. Write this exact sentence, adapting the context to their field: "Disconnected systems increase operational uncertainty, reduce reporting and forecasting reliability, and limit visibility across business operations, making strategic planning significantly less predictable."
                   * Paragraph 2 (Tactical Adaptation to Constraints): "Given your current constraints, a full platform migration would introduce unnecessary complexity and operational risk. A lightweight integration layer is a more appropriate approach, enabling better data visibility while preserving existing workflows."
                   * End this section with this exact sentence (no quote marks): "The objective is not to replace your existing ecosystem, but to make it work as a unified decision-support platform."

                5. SECTION 4: EXECUTIVE RECOMMENDATION (MANDATORY FORMAT)
                   Include a highlighted, concise callout box with this exact layout:
                   > **SECTION 4: EXECUTIVE RECOMMENDATION**
                   >
                   > {"Start with a structured discovery phase to validate the operational assumptions before defining the integration roadmap." if is_unconfirmed else "Start with data integration rather than software replacement."}
                   > {"A phased analysis strategy will deliver clarity on data sources while respecting constraints and minimizing disruption." if is_unconfirmed else "A phased modernization strategy will deliver immediate operational and organizational visibility while respecting constraints and minimizing disruption."}

                6. SECTION 5: EXPECTED BUSINESS IMPACT (MANDATORY MBB FORMAT)
                   Output a clean bulleted list detailing the exact strategic effects under the title "### 📈 Expected Business Impact". Use active, verb-first structures (e.g., "Improve...", "Increase...", "Accelerate...", "Strengthen...", "Reinforce...") strictly aligned with their stated Pain:
                   - **[Action Verb] [Dynamic impact matching Pain - e.g., Improve reliability of organizational forecasting]**
                   - **[Action Verb] [Dynamic impact matching Root Causes or Discovery verification]**
                   - **[Action Verb] [Dynamic impact matching Decision Lens]**

                7. SECTION 6: IMMEDIATE PRIORITIES (MANDATORY FORMAT)
                   Output a highly-structured numbered list under the title "### 🎯 Immediate Priorities". Ensure zero repetitive phrasing from prior sections.
                   Use active, consistent verbs to dictate 3 dynamic, slot-driven immediate priorities.
                """

                try:
                    final_diag = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "user", "content": prompt_final}]
                    ).choices[0].message.content

                    # Display Recommendation Header and Metadata in CSS Styled Box
                    st.markdown(f"""
                    <div class="recommendation-box">
                        <div class="{badge_class}">⚠️ EXECUTIVE RISK LEVEL: {risk_level}</div>
                        <div style="font-size: 0.9em; margin-top: -10px; color: #FFD2D2;">
                            <b>Reason:</b><br>
                            • Low report and forecast reliability based on fragmented data<br>
                            • Limited data visibility across active organizational layers<br>
                            • Operational constraints preventing total system overhauls
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Render Markdown output strictly OUTSIDE of HTML structures
                    st.markdown(final_diag)

                    # Dynamic Confidence Level Notification
                    if is_unconfirmed:
                        st.markdown(f"""
                        <div class="confidence-box">
                            <b>📋 Diagnostic Confidence: MEDIUM</b><br>
                            Additional operational discovery is required to confirm the underlying technical root causes before defining a rigid implementation roadmap.
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
                        * **Transformation Strategy:** {"Structured operational discovery & mapping" if is_unconfirmed else "Lightweight secure integration"}
                        """)

                    st.markdown("---")
                    st.subheader("📊 Operational Diagnosis")

                    st.error(f"""**🔴 Core Business Pain:**  
{st.session_state.slots.get('Pain', 'Empty')}""")

                    st.warning(f"""**⚙️ Technical Root Causes:**  
{root_cause_val}""")

                    st.info(f"""**⚠️ Constraints & Limits:**  
{st.session_state.slots.get('Limits', 'Empty')}""")

                except Exception as e:
                    st.error(f"Error generating blueprint: {e}")
