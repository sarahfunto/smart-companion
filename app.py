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
    if not client:
        return
    
    prompt_analyse = f"""
    Current Interview Stage: {stages[str(current_stage)]}
    Manual Web Context Provided: {context_web}
    Latest Client Input: "{user_text}"
    Current Slot State: {json.dumps(st.session_state.slots)}
    Current Psychological Tags: {json.dumps(st.session_state.tags)}

    TASK:
    1. Analyze the client input and update any relevant Slots or Psychological Tags if new information is revealed.
    2. Formulate the next strategic question or response for the consultant to guide the interview.
    
    Format your response STRICTLY as a JSON object with these exact keys:
    {{
        "slots_update": {{ "Role": "...", "Trigger": "...", "Tech": "...", "Pain": "...", "Success": "...", "Limits": "..." }},
        "tags_update": {{ "Lens": "...", "Fear": "..." }},
        "ai_guidance": "Your direct strategic advice/next question here"
    }}
    Only fill fields in slots_update or tags_update if they change from 'Empty' or 'None'. Otherwise keep current values.
    """
    
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
        
        # Update slots if new values are found
        for k, v in result.get("slots_update", {}).items():
            if v and v != "Empty":
                st.session_state.slots[k] = v
                
        # Update tags
        for k, v in result.get("tags_update", {}).items():
            if v and v != "None":
                st.session_state.tags[k] = v
                
        # Update agent guidance
        st.session_state.ai_guidance = result.get("ai_guidance", "Continue the interview building on this response.")
        
    except Exception as e:
        st.error(f"API Analysis Error: {str(e)}")

st.title("🎙️ Smart Companion — Expert Workspace")

# ==========================================
# 🌐 SIDEBAR: MANUAL WEB CONTEXT INJECTION
# ==========================================
st.sidebar.markdown("## 🔍 Live Context Injection")
st.sidebar.markdown("*Paste background information about the target company or Limor's test notes below before running the interview.*")

web_context_input = st.sidebar.text_area(
    "📝 Corporate Profile / Web Context", 
    height=200,
    placeholder="Example: Microsoft Corp. Experiencing significant reporting bottlenecks in mid-market auditing fields. Executive board is highly risk-averse regarding external data compliance..."
)

if st.sidebar.button("💾 Synchronize Context"):
    st.sidebar.success("Brain updated with the latest background insights!")

# MAIN INTERFACE WORKFLOW
st.markdown(f"### Stage {st.session_state.stage} / 7")

col1, col2 = st.columns([2, 1])

with col1:
    # Live Strategy Guidance Box
    st.info(f"**Smart Companion Strategy:** {st.session_state.ai_guidance}")
    
    st.markdown(f"**Current Phase Objective:** {stages[str(st.session_state.stage)]}")
    
    # MANUAL TEXT INPUT AREA (REPLACING THE VOCAL MODULE)
    st.markdown("---")
    manual_input = st.text_area("⌨️ Client Input (Type what the prospect says):", height=100, placeholder="Example: We mostly rely on heavy Excel workbooks. It is slow and I am terrified of losing data integrity...")
    
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

# FINAL REPORT SUMMARY GENERATED AT STAGE 7
if st.session_state.stage == 7:
    st.balloons()
    st.header("📋 Final Strategic Diagnostic")
    
    rec_text = "Based on the structural technical and behavioral profile of the prospect, Smart Companion recommends a phased rollout strategy. "
    if "Excel" in st.session_state.slots['Tech'] or "Manual" in st.session_state.slots['Tech']:
        rec_text += "Priority #1 must be the immediate migration of legacy manual flows into a unified database infrastructure. "
    if "Time Loss" in st.session_state.slots['Pain'] or "Operational" in st.session_state.slots['Pain']:
        rec_text += "Deploying a tailored LLM pipeline for automated document parsing will address the core operational bottleneck from day one. "
    if "Limits" in st.session_state.slots['Limits'] or "Budget" in st.session_state.slots['Limits']:
        rec_text += "Structure your upcoming commercial offer around an ROI-guaranteed initial MVP to completely neutralize their spending fears."
    else:
        rec_text += "Propose an enterprise-wide automation blueprint focused directly on large-scale optimization."

    st.markdown(f"""
    <div class="recommendation-box">
        <h3>🧠 Smart Companion's Advisory Insights:</h3>
        <p>{rec_text}</p>
        <hr style="border-color: #134074;">
        <small>💡 <b>Closing Tip:</b> Deliver your final pitch using a <b>{st.session_state.tags['Lens']}</b> tone, and address their critical friction threshold directly: <i>\"{st.session_state.tags['Fear']}\"</i>.</small>
    </div>
    """, unsafe_allow_html=True)
