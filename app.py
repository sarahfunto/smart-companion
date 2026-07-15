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
You are an expert B2B sales psychologist and high-level enterprise consultant. Your core mission is to guide a discovery interview with a potential client by applying a rigorous analytical framework. 

[PSYCHOLOGICAL PROFILING RULES]
- Decision Filter (Lens): Choose the lens based on the prospect's actual ROLE and primary responsibilities, NOT just technical keywords. 
* If a non-technical role (Sales, Marketing, HR, CFO) mentions database terms (SQL, Postgres, Access) but does not code or build architecture, do NOT classify them as "Technical". Use "Business/ROI-Driven" or "Risk/Compliance-Locked" instead.
          
- Identified Core Fear (Fear): Extract ONLY anxieties, pressures, or vulnerabilities explicitly stated or directly implied by the prospect (e.g., losing renewals, losing board trust, untrustworthy data forecasting). 
* NEVER hallucinate external threats. Do NOT invent fears about "competitors", "market disruption", or "being overshadowed" unless the user explicitly mentions competition.
          
# ---------------------------------------------------------------------------------
        
Output format should be JSON with keys: Role, CompanySize, Tech, Pain, Lens, Fear...

Your reasoning layer must constantly cross-reference three dimensions based on the conversation and the live web context provided:
1. OPERATIONAL PAIN: Identify the exact bottlenecks, inefficient workflows, or financial leaks in their daily operations.
2. TECHNICAL MATURITY: Assess their current infrastructure, their readiness to adopt AI solutions, and their technical limitations.
3. EMOTIONAL FEAR: Uncover the unspoken stakes for the leader (e.g., fear of losing market share, anxiety over team management, stress regarding data privacy, or fear of tech obsolescence).

CRITICAL EXTRACTION & ENTITY RULES:
- Distinguish strictly between "Role" and "CompanySize". 
- "Role" is the user's personal job title or function (e.g., CEO, Owner, Chief AI Officer, Legal Counsel). Do NOT put company descriptions here.
- "CompanySize" is the scale or type of the organization (e.g., Mid-sized company, SMB, Startup, Enterprise, 10 employees).
- Do not sound like a standard chatbot. Act as a sharp, empathetic, and strategic peer.
- Keep your questions precise, single-focused, and designed to move the client seamlessly through the interview stages.
- Even if the client gives short, confusing, or evasive answers, use your psychological framework to stay grounded, dig deeper, and guide them back on track with empathy.
"""

st.set_page_config(page_title="AI Advisor - Smart Companion", page_icon="🎙️", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    
    /* Default empty status box */
    .status-box-empty { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #1E2329; 
        border: 1px solid #3E444B; 
        margin-bottom: 8px; 
        color: #6C757D;
    }
    
    /* Successfully validated box (Success Green) */
    .status-box-filled { 
        padding: 12px; 
        border-radius: 10px; 
        background-color: #155724; 
        border: 2px solid #28a745; 
        margin-bottom: 8px; 
        color: #D4EDDA;
        font-weight: bold;
    }
    
    /* AI Recommendation container */
    .recommendation-box {
        padding: 20px;
        border-radius: 15px;
        background-color: #0B2545;
        border: 2px solid #134074;
        color: #EEF4F8;
        margin-top: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# SESSION STATE INITIALIZATION (Updated to 4 Stages and added CompanySize slot)
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'CompanySize': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial client statement to start the strategic analysis."

# Raccourci à 4 étapes selon les souhaits de Limor
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
        "  \"slots\": { \"Role\": \"...\", \"CompanySize\": \"...\", \"Tech\": \"...\", \"Pain\": \"...\", \"Limits\": \"...\" },\n"
        "  \"tags\": { \"Lens\": \"...\", \"Fear\": \"...\" },\n"
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
        
        # Update and merge memory (Slots)
        new_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in new_slots and new_slots[key] not in ["Empty", "", "None", "Keep existing or update"]:
                st.session_state.slots[key] = new_slots[key]
        
        # Dynamic update of Psychological Tags
        new_tags = result.get("tags", {})
        for key in st.session_state.tags:
            if key in new_tags and new_tags[key] not in ["None", ""]:
                st.session_state.tags[key] = new_tags[key]
        
        # Smart Sensitivity Override
        current_role = str(st.session_state.slots.get('Role', '')).upper()
        current_tech = str(st.session_state.slots.get('Tech', '')).upper()
        
        for tag_key in st.session_state.tags:
            if "DECISION" in tag_key.upper() or "LENS" in tag_key.upper():
                if "CTO" in current_role or "AWS" in current_tech or "POSTGRESQL" in current_tech:
                    st.session_state.tags[tag_key] = "Technical / ROI-Driven"
                elif "COMPLIANCE" in current_role or "RISK" in current_role or "SERVER" in current_tech:
                    st.session_state.tags[tag_key] = "Risk / Compliance-Locked"
            
        return result.get("ai_guidance", "Analysis complete.")
    except Exception as e:
        st.error(f"Error calling OpenAI: {e}")
        return "Error analyzing input."

st.title("🎙️ Smart Companion — Expert Workspace")

# ==========================================
# 🌐 SIDEBAR: MANUAL WEB CONTEXT INJECTION
# ==========================================
st.sidebar.markdown("## 🔍 Live Context Injection")
st.sidebar.markdown("*Paste background information about the target company or Limor's test notes below before running the interview.*")

web_context_input = st.sidebar.text_area(
    "📝 Corporate Profile / Web Context", 
    height=200,
    placeholder="Example: Microsoft Corp. Experiencing significant reporting bottlenecks in mid-market auditing fields..."
)

if st.sidebar.button("💾 Synchronize Context"):
    st.sidebar.success("Brain updated with the latest background insights!")

# DISPLAY CURRENT STAGE & CONCRETE OPEN QUESTION
st.markdown(f"### 💬 Interview Progress: Step {st.session_state.stage} / 4")

# Questions adaptées au flux condensé en 4 étapes
stage_questions = {
    "1": "Who am I speaking with today, what is the scale of your organization, and what corporate trigger brought you here?",
    "2": "What does your current software infrastructure look like? Are your daily workflows mostly manual or cloud-based?",
    "3": "Where are your teams losing the most hours, and if we deployed AI tomorrow, what are your core operational fears or constraints?",
    "4": "Reviewing your strategic situation: Here is what we know. Do you want to add, modify, or complete any data before receiving your final custom roadmap?"
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
    
    # WORKFLOW NAVIGATION
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
    
    fear_class = "status-box-filled" if st.session_state.tags['Fear'] != "None" else "status-box-empty"
    st.markdown(f"<div class='{fear_class}'><b>Identified Core Fear (Fear):</b> {st.session_state.tags['Fear']}</div>", unsafe_allow_html=True)

# FINAL DIAGNOSTIC AT STAGE 4 WITH SECURITY THRESHOLD (TRIGGER)
if st.session_state.stage == 4:
    st.markdown("---")
    st.header("📋 Comprehensive Strategic Blueprint")
    
    # Initialize session state variable to track if step 4 was submitted
    if 'diagnostic_ready' not in st.session_state:
        st.session_state.diagnostic_ready = False

    # Trigger diagnostic if stage is 4 and we have a transcript recorded
    if st.session_state.transcript:
        st.session_state.diagnostic_ready = True

    # SECURITY TRIGGER: Count how many critical slots have been filled
    filled_slots_count = sum(1 for val in st.session_state.slots.values() if val != "Empty")
    
    if st.session_state.diagnostic_ready:
        if filled_slots_count < 3:
            st.error("⚠️ Diagnostic Blocked: Insufficient Data.")
            st.warning("You must provide more details to unlock the diagnostic.")
        else:
            st.balloons()
            with st.spinner("Generating deep expert diagnostic reflecting blind spots..."):
                
                # STRICT SYSTEM INSTRUCTIONS TO PREVENT HALLUCINATIONS AND SIZE MISMATCH
                prompt_final = f"""
                Act as an elite, hyper-logical B2B Sales Consultant and Psychologist. 
                Analyze this precise prospect profile:
                - Role: {st.session_state.slots['Role']}
                - Exact Company Size: {st.session_state.slots['CompanySize']}
                - Technical Stack: {st.session_state.slots['Tech']}
                - Core Pain: {st.session_state.slots['Pain']}
                - Psychological Lens: {st.session_state.tags.get('Lens', 'Business-Driven')}
                - Extracted Fear: {st.session_state.tags.get('Fear', 'Operational Inefficiency')}
                
                Generate a highly tailored 3-paragraph diagnostic based STRICTLY on the above parameters. Avoid these critical mistakes:
                
                1. COMPANY SIZE COHERENCE (CRITICAL): You must align your analysis with the EXACT company scale ({st.session_state.slots['CompanySize']}). 
                   - If company size is small (e.g., 11 employees, under 50 people), do NOT refer to them as a "mid-sized enterprise" or "large enterprise". Treat them as a small, compact, or agile operation. Adapt the scale of your recommendations to a small team.
                
                2. STRICT FEAR ADHERENCE: Focus purely on their internal, expressed fears: {st.session_state.tags.get('Fear', 'Operational Inefficiency')}. 
                   - Do NOT invent external market threats, competitor pressure, or "being overshadowed" unless explicitly stated in their profile. Keep the anxiety centered on internal operations, forecasting trust, and board/investor relationships.
                
                3. REALISTIC ROADMAP: Provide a budget-conscious, highly operational 3-step action plan that a company of {st.session_state.slots['CompanySize']} can realistically implement without massive overhead.
                
                Keep the tone consultative, direct, and elite. No generic AI fluff.
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
                    st.write(f"• **Tech Maturity:** {st.session_state.slots['Tech']}")
                    st.write(f"• **Core Operational Pain:** {st.session_state.slots['Pain']}")
                except Exception as e:
                    st.error(f"Error generating blueprint: {e}")
    else:
        st.info("ℹ️ The final strategic blueprint will appear here once you submit your response above.")
