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

Your reasoning layer must constantly cross-reference three dimensions based on the conversation and the live web context provided:
1. OPERATIONAL PAIN: Identify the exact bottlenecks, inefficient workflows, or financial leaks in their daily operations.
2. TECHNICAL MATURITY: Assess their current infrastructure, their readiness to adopt AI solutions, and their technical limitations.
3. EMOTIONAL FEAR: Uncover the unspoken stakes for the leader (e.g., fear of losing market share, anxiety over team management, stress regarding data privacy, or fear of tech obsolescence).

CRITICAL INSTRUCTIONS:
- Do not sound like a standard chatbot. Act as a sharp, empathetic, and strategic peer.
- Leverage the provided Web Context to ask deeply relevant, tailored questions that prove you understand their specific market positioning and corporate updates.
- Adapt your tone dynamically: maintain a pragmatic, solution-oriented approach, focusing heavily on operational efficiency rather than generic AI buzzwords.
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

# SESSION STATE INITIALIZATION
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Empty', 'Trigger': 'Empty', 'Tech': 'Empty', 'Pain': 'Empty', 'Success': 'Empty', 'Limits': 'Empty'}
if 'tags' not in st.session_state: st.session_state.tags = {'Lens': 'Standard', 'Fear': 'None'}
if 'transcript' not in st.session_state: st.session_state.transcript = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome to the simulation. Input the initial client statement to start the strategic analysis."

stages = {
    "1": "Phase 1: Alignment & Trigger Detection (Role Assessment & Contextual Validation)",
    "2": "Phase 2: Technical Maturity Diagnostics (Infrastructure Readiness & Evaluator)",
    "3": "Phase 3: Deep Pain Architecture (Operational Pain Discovery & Root Cause)",
    "4": "Phase 4: Executive Psychology Profiling (AI Literacy & Emotional Fear Mapping)",
    "5": "Phase 5: Strategic Anchoring (Growth Alignment & Blocker Identification)",
    "6": "Phase 6: Active Alignment & Gap Closing (Mirroring & Sync Confirmation)",
    "7": "Phase 7: Value Delivery & Conversion (Diagnostic Output & Blueprint)"
}

# AI ANALYSIS ENGINE FUNCTION
def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text:
        return None

    current_slots = st.session_state.slots
    current_tags = st.session_state.tags

    # Construction du prompt sans formatage JSON brut à l'intérieur pour éviter le bug d'accolades
    prompt_analyse = (
        f"Current Interview Stage: {stages[str(current_stage)]}\n"
        f"Manual Web Context Provided: {context_web}\n"
        f"Latest Client Input: {user_text}\n"
        f"Current Slot State (Already Filled): {json.dumps(current_slots)}\n"
        f"Current Psychological Tags: {json.dumps(current_tags)}\n\n"
        "TASK:\n"
        "1. Analyze the client's input. Identify technical facts AND emotional signals.\n"
        "2. Update the Slots and Psychological Tags. CRITICAL MEMORY RULE: You MUST PRESERVE and carry forward all previously filled slots from the 'Current Slot State' if they are not explicitly replaced by the latest input. Do NOT overwrite existing data with 'Empty' or blanks.\n"
        "3. Formulate the next strategic recommendation for the consultant.\n\n"
        "Format your response STRICTLY as a JSON object with these exact keys:\n"
        "{\n"
        "  \"slots\": { \"Role\": \"...\", \"Trigger\": \"...\", \"Tech\": \"...\", \"Pain\": \"...\", \"Success\": \"...\", \"Limits\": \"...\" },\n"
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
        
        # Dynamic and sensitive update of the Psychological Tags
        new_tags = result.get("tags", {})
        for key in st.session_state.tags:
            if key in new_tags and new_tags[key] not in ["None", ""]:
                # If the AI detects a change in posture, update immediately
                st.session_state.tags[key] = new_tags[key]
            
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
st.markdown(f"### 💬 Interview Progress: Step {st.session_state.stage} / 7")

stage_questions = {
    "1": "Who am I speaking with today, and what corporate trigger brought you to explore AI automation solutions right now?",
    "2": "What does your current data and software infrastructure look like? Are your daily workflows mostly manual or already cloud-based?",
    "3": "Where are your teams losing the most hours or money today? What is the single biggest operational bottleneck you face?",
    "4": "If we deployed an AI framework tomorrow, what are you most worried about? Is it data privacy, team adoption, or return on investment?",
    "5": "What are your core resource constraints regarding budget or timeline, and who else on the executive board needs to approve this project?",
    "6": "Based on what we discussed, does this summary match your expectations, or is there any gap left to close before we move forward?",
    "7": "Reviewing your strategic diagnostic report: What are your immediate thoughts on this custom automation roadmap?"
}

# Big user-friendly open question
st.subheader(f"👉 {stage_questions[str(st.session_state.stage)]}")

# Small methodology subtitle underneath
st.markdown(f"<small style='color: #888888; font-style: italic;'>Methodology Context — {stages[str(st.session_state.stage)]}</small>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns([2, 1])

with col1:
    # Affiche la recommandation en temps réel stockée en mémoire si elle existe, sinon le message par défaut
    guidance_text = st.session_state.get('ai_guidance', "Welcome to the simulation. Input the initial client statement to start the strategic analysis.")
    st.info(f"Smart Companion Strategy Insight: {guidance_text}")
    
    st.markdown(f"**Current Phase Objective:** {stages[str(st.session_state.stage)]}")
    
    # MANUAL TEXT INPUT AREA (REPLACING THE VOCAL MODULE)
    st.markdown("---")
    
    # ON UTILISE UNE CLÉ DYNAMIQUE LIÉE AU STAGE POUR FORCER LA RÉINITIALISATION
    input_key = f"client_input_stage_{st.session_state.stage}"
    manual_input = st.text_area("⌨️ Client Input (Type what the prospect says):", height=100, placeholder="Example: We mostly rely on heavy Excel workbooks. It is slow and I am terrified of losing data integrity...", key=input_key)
    
    if st.button("⚡ Validate and Analyze Input"):
        if manual_input:
            st.session_state.transcript = manual_input
            with st.spinner("Processing framework analytical layers..."):
                analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
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
        if st.session_state.stage < 7:
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

# FINAL DIAGNOSTIC GENERATED BY AI AT STAGE 7
if st.session_state.stage == 7:
    st.balloons()
    st.header("📋 Comprehensive Strategic Blueprint")
    
    # AI generates a tailored, deep diagnostic based on the interview history
    with st.spinner("Generating expert diagnostic..."):
        prompt_final = f"""
        Act as a top-tier B2B consultant. Based on the following interview data:
        Slots: {json.dumps(st.session_state.slots)}
        Tags: {json.dumps(st.session_state.tags)}
        
        Write a professional, 3-paragraph diagnostic:
        1. Executive Summary: What is the real, hidden bottleneck?
        2. Technical & Operational Roadmap: A concrete, 3-step action plan.
        3. Closing Strategy: How to win the trust of this specific prospect based on their fears.
        Keep it sharp, analytical, and highly tailored to the data above.
        """
        
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
    st.write(f"• **Tech Maturity:** {st.session_state.slots['Tech']}")
    st.write(f"• **Core Pain:** {st.session_state.slots['Pain']}")
    st.write(f"• **Success Metric:** {st.session_state.slots['Success']}")
    st.write(f"• **Strategic Limits:** {st.session_state.slots['Limits']}")
