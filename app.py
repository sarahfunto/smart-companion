import streamlit as st
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLES
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Companion - Executive Profiler",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Smart Companion")
st.caption("AI-Powered Executive Profiling & Diagnostic Assistant")

# OpenAI Client Setup
api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("Please configure your OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=api_key)

# -----------------------------------------------------------------------------
# 2. PYDANTIC SCHEMAS (FOR CALL B EXTRACTION)
# -----------------------------------------------------------------------------
class ProfileAttribute(BaseModel):
    value: Optional[str] = Field(default=None, description="Extracted attribute value")
    confidence: float = Field(default=0.0, description="Confidence score between 0.0 and 1.0")
    source: str = Field(default="stated", description="Source: 'stated', 'inferred', or 'manual'")
    evidence: Optional[str] = Field(default=None, description="Exact verbatim quote supporting this extraction")
    conflict_flag: bool = Field(default=False, description="True if a contradiction with previous data is detected")
    old_value: Optional[str] = Field(default=None, description="Previous value if a conflict exists")

class FactsGroup(BaseModel):
    industry: ProfileAttribute = Field(default_factory=ProfileAttribute)
    company_size: ProfileAttribute = Field(default_factory=ProfileAttribute)
    tools: ProfileAttribute = Field(default_factory=ProfileAttribute)
    org_context: ProfileAttribute = Field(default_factory=ProfileAttribute)

class InterpretationGroup(BaseModel):
    primary_pain: ProfileAttribute = Field(default_factory=ProfileAttribute)
    trigger: ProfileAttribute = Field(default_factory=ProfileAttribute)
    lens: ProfileAttribute = Field(default_factory=ProfileAttribute)
    fear: ProfileAttribute = Field(default_factory=ProfileAttribute)

class ExecutiveProfile(BaseModel):
    facts: FactsGroup = Field(default_factory=FactsGroup)
    interpretation: InterpretationGroup = Field(default_factory=InterpretationGroup)

# -----------------------------------------------------------------------------
# 3. SYSTEM PROMPTS
# -----------------------------------------------------------------------------
CALL_A_SYSTEM_PROMPT = """
You are a senior executive AI strategy consultant. You are warm, empathetic, and highly perceptive.

YOUR OBJECTIVE:
Conduct a step-by-step diagnostic interview with a business leader (CEO / Executive) to understand their operational context, pain points, and digital readiness.

STRICT CONVERSATIONAL RULES:
1. EMPATHY & VALIDATION: Always acknowledge and validate the emotional weight or operational challenge expressed by the executive before moving forward.
2. ONE QUESTION AT A TIME: Never ask more than one question per turn. Keep it focused and digestible.
3. CONCRETE CHOICES: Executives don't always know technical AI jargon. Give simple, everyday examples or options (e.g., "Are you mostly using specialized software, heavy Excel sheets, or manual processes?").
4. STEP-BY-STEP GUIDANCE: Take control of the interview flow in this logical sequence:
   - Step 1: Confirm their role and industry.
   - Step 2: Ask about company/team size.
   - Step 3: Discover current toolings and operational workflows.
   - Step 4: Identify the primary pain point or bottleneck.
   - Step 5: Understand strategic goals and priorities.

Do not pitch technical solutions immediately. Your priority is to ask the next natural question to fill in the diagnostic profile seamlessly.
"""

CALL_B_SYSTEM_PROMPT = """
You are a structured parallel data extractor. Your job is to analyze the ongoing conversation between an executive and an AI consultant and populate the JSON profile schema.

CRITICAL RULES:
1. Extract facts (industry, size, tools) and interpretations (pain points, triggers, cognitive lenses, fears).
2. For every field, provide:
   - value: extracted string or null
   - confidence: score from 0.0 to 1.0
   - source: "stated" (explicitly said), "inferred" (deduced), or "manual"
   - evidence: exact verbatim quote from the dialogue
3. CONFLICT DETECTION: If the user explicitly contradicts a previously established value (e.g., changing primary pain from 'turnover' to 'margin pressure'), set 'conflict_flag' to true, save the previous value in 'old_value', and update 'value' to the new statement.
4. Output strict JSON matching the requested schema without conversational text.
"""

# -----------------------------------------------------------------------------
# 4. SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Welcome! I am your AI Strategy Assistant. To help tailor our conversation to your exact situation: **what is your executive role and which industry are you in?**"
        }
    ]

if "profile" not in st.session_state:
    st.session_state.profile = ExecutiveProfile().model_dump()

# -----------------------------------------------------------------------------
# 5. LAYOUT: TWO COLUMNS (CHAT & LIVE PROFILE)
# -----------------------------------------------------------------------------
col_chat, col_profile = st.columns([3, 2])

# --- LEFT COLUMN: CONVERSATIONAL AGENT (CALL A) ---
with col_chat:
    st.subheader("💬 Executive Consultation")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # User Input
    if user_input := st.chat_input("Type your answer here..."):
        # 1. Show user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. Call A: Generate Assistant Response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing response..."):
                response_A = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": CALL_A_SYSTEM_PROMPT},
                        *st.session_state.messages
                    ],
                    temperature=0.7
                )
                assistant_reply = response_A.choices[0].message.content
                st.markdown(assistant_reply)
                st.session_state.messages.append({"role": "assistant", "content": assistant_reply})

        # 3. Call B: Structured JSON Extraction in Parallel
        try:
            conversation_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            
            response_B = client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": CALL_B_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Current Profile JSON:\n{json.dumps(st.session_state.profile)}\n\nFull Conversation:\n{conversation_text}"}
                ],
                response_format=ExecutiveProfile,
                temperature=0.0
            )
            
            extracted_profile = response_B.choices[0].message.parsed
            st.session_state.profile = extracted_profile.model_dump()
            st.rerun()

        except Exception as e:
            st.error(f"Extraction Error (Call B): {e}")

# --- RIGHT COLUMN: LIVE PROFILE & GATEKEEPER ---
with col_profile:
    st.subheader("📊 Live Strategic Profile")

    profile_data = st.session_state.profile
    facts = profile_data.get("facts", {})
    interp = profile_data.get("interpretation", {})

    # Visual Badges for Conflicts
    has_conflict = any(
        field.get("conflict_flag")
        for group in [facts, interp]
        for field in group.values()
        if isinstance(field, dict)
    )

    if has_conflict:
        st.warning("⚠️ CONFLICT DETECTED: Contradictory statements identified in conversation.")

    # Gatekeeper Evaluation
    has_size = bool(facts.get("company_size", {}).get("value"))
    has_pain = bool(interp.get("primary_pain", {}).get("value"))
    has_tools = bool(facts.get("tools", {}).get("value"))

    gatekeeper_unlocked = has_size and has_pain and has_tools

    if gatekeeper_unlocked:
        st.success("🟢 Diagnostic Gatekeeper: UNLOCKED")
    else:
        st.error("🔴 Diagnostic Gatekeeper: LOCKED (Insufficient context)")

    # Display Profile JSON Tree
    with st.expander("🔍 Detailed JSON Profile", expanded=True):
        st.json(profile_data)

    # Basic Diagnosis Trigger
    st.divider()
    if st.button("🧪 Request Strategic Diagnosis", disabled=not gatekeeper_unlocked):
        with st.spinner("Generating Strategic Report..."):
            diag_prompt = f"Based on this executive profile, generate a concise 3-bullet strategic AI diagnosis:\n{json.dumps(profile_data)}"
            diag_res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": diag_prompt}]
            )
            st.info(diag_res.choices[0].message.content)
