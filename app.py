import streamlit as st
import json
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Companion - Executive Profiler",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Smart Companion")
st.caption("AI-Powered Executive Profiling & Strategic Diagnostic Assistant")

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("Please configure your OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=api_key)

# -----------------------------------------------------------------------------
# 2. PYDANTIC SCHEMAS (CALL B)
# -----------------------------------------------------------------------------
class ProfileAttribute(BaseModel):
    value: Optional[str] = Field(default=None)
    confidence: float = Field(default=0.0)
    source: str = Field(default="stated")
    evidence: Optional[str] = Field(default=None)
    conflict_flag: bool = Field(default=False)
    old_value: Optional[str] = Field(default=None)

class FactsGroup(BaseModel):
    industry: ProfileAttribute = Field(default_factory=ProfileAttribute)
    company_size: ProfileAttribute = Field(default_factory=ProfileAttribute)
    tools: ProfileAttribute = Field(default_factory=ProfileAttribute)

class InterpretationGroup(BaseModel):
    primary_pain: ProfileAttribute = Field(default_factory=ProfileAttribute)
    trigger: ProfileAttribute = Field(default_factory=ProfileAttribute)
    fear: ProfileAttribute = Field(default_factory=ProfileAttribute)

class ExecutiveProfile(BaseModel):
    facts: FactsGroup = Field(default_factory=FactsGroup)
    interpretation: InterpretationGroup = Field(default_factory=InterpretationGroup)

# -----------------------------------------------------------------------------
# 3. PROMPTS
# -----------------------------------------------------------------------------
CALL_A_SYSTEM_PROMPT = """
You are a warm, highly empathetic senior AI strategy consultant speaking directly to an executive.
Acknowledge their stress, validate their operational challenges, and ask ONE clear, friendly question at a time to guide the conversation.
"""

CALL_B_SYSTEM_PROMPT = """
Extract structured key-value profiles from the conversation into the given JSON format.
Set conflict_flag=true if the user contradicts an earlier statement.
"""

HUMAN_DIAGNOSIS_PROMPT = """
You are a veteran executive peer and strategist. Write a personalized, highly human diagnostic report for this leader based on their profile data.

DO NOT use generic AI template bullet points like "Upgrade Infrastructure" or "Leverage AI".
Instead, write with deep empathy, clear executive authority, and actionable advice addressing their exact pain points, company size, and team reality.

Structure your report into 3 distinct parts:
1. 💡 **The Reality Check**: Acknowledge their situation with genuine empathy (mention their team size, their tools, and the real pressure they feel).
2. 🚀 **Immediate High-Impact Action**: Give ONE pragmatic first step tailored specifically to their bottleneck (e.g. automating a specific repetitive friction point instead of replacing their whole system).
3. 🛡️ **Reassurance & Strategic Direction**: Offer clear strategic reassurance on how to close the gap with competitors without overwhelming their employees.
"""

# -----------------------------------------------------------------------------
# 4. INITIALIZATION
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Welcome! I'm your strategic AI companion. To start, could you share your executive role and the industry you're operating in?"
        }
    ]

if "profile" not in st.session_state:
    st.session_state.profile = ExecutiveProfile().model_dump()

# -----------------------------------------------------------------------------
# 5. LAYOUT
# -----------------------------------------------------------------------------
col_chat, col_profile = st.columns([3, 2])

# --- LEFT: CHAT ---
with col_chat:
    st.subheader("💬 Executive Consultation")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                res_A = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": CALL_A_SYSTEM_PROMPT}, *st.session_state.messages],
                    temperature=0.7
                )
                reply = res_A.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

        # Extraction Call B
        try:
            conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            res_B = client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": CALL_B_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Current Profile:\n{json.dumps(st.session_state.profile)}\n\nConversation:\n{conv_text}"}
                ],
                response_format=ExecutiveProfile,
                temperature=0.0
            )
            st.session_state.profile = res_B.choices[0].message.parsed.model_dump()
            st.rerun()
        except Exception as e:
            st.error(f"Extraction error: {e}")

# --- RIGHT: LIVE VISUAL CARDS & DIAGNOSIS ---
with col_profile:
    st.subheader("📊 Strategic Live Profile")

    p = st.session_state.profile
    facts = p.get("facts", {})
    interp = p.get("interpretation", {})

    # Helper function for rendering clean status cards
    def render_card(label, item):
        val = item.get("value")
        conflict = item.get("conflict_flag", False)
        
        if conflict:
            st.warning(f"**{label}:** {val} *(⚠️ Changed from: {item.get('old_value')})*")
        elif val:
            st.success(f"**{label}:** {val}")
        else:
            st.info(f"**{label}:** *Not specified yet*")

    st.markdown("### 🏢 Operational Facts")
    render_card("Industry", facts.get("industry", {}))
    render_card("Company Size", facts.get("company_size", {}))
    render_card("Current Tools", facts.get("tools", {}))

    st.markdown("### 🎯 Strategic Insights")
    render_card("Primary Pain Point", interp.get("primary_pain", {}))
    render_card("Market Trigger", interp.get("trigger", {}))
    render_card("Executive Fear / Concern", interp.get("fear", {}))

    st.divider()

    # Gatekeeper Status
    has_size = bool(facts.get("company_size", {}).get("value"))
    has_tools = bool(facts.get("tools", {}).get("value"))
    has_pain = bool(interp.get("primary_pain", {}).get("value"))
    unlocked = has_size and has_tools and has_pain

    if unlocked:
        st.success("🟢 Diagnostic Gatekeeper: READY")
    else:
        st.error("🔴 Diagnostic Gatekeeper: LOCKED (Awaiting key context)")

    if st.button("🧪 Generate Human Diagnostic Report", disabled=not unlocked, type="primary"):
        with st.spinner("Crafting tailored executive diagnosis..."):
            diag_res = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": HUMAN_DIAGNOSIS_PROMPT},
                    {"role": "user", "content": f"Profile Data:\n{json.dumps(p)}"}
                ],
                temperature=0.7
            )
            st.markdown("---")
            st.markdown(diag_res.choices[0].message.content)
