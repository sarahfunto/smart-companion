import streamlit as st
import json
import os
import re
import requests  # (Webhook Make / Zapier)
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DIRECTORY SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Companion - Executive Profiler",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Smart Companion")
st.caption("AI-Powered Executive Profiling & Strategic Diagnostic Assistant")

DATA_DIR = "saved_profiles"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("Please configure your OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=api_key)

# Webhook URL for Make / Zapier / Google Sheets
WEBHOOK_URL = st.secrets.get("WEBHOOK_URL", None)

# -----------------------------------------------------------------------------
# 2. PYDANTIC SCHEMAS
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
# 3. SYSTEM PROMPTS
# -----------------------------------------------------------------------------
CALL_A_SYSTEM_PROMPT = """
You are a warm, highly empathetic senior AI strategy consultant speaking directly to an executive.

YOUR GOAL:
Guide the executive step-by-step to gather operational facts and strategic insights.

BALANCED CONVERSATIONAL RULES:
1. ALWAYS ACKNOWLEDGE PREVIOUSLY EXPRESSED PAIN:
   - If the user mentioned a specific problem (e.g., kitchen staff attendance, supplier delays), acknowledge it warmly first in ONE sentence before asking your follow-up.
   - Example: "I completely hear you on the kitchen staff attendance issues — that constant reshuffling must be exhausting."

2. RE-PROMPT FOR MISSING FACTS WITH BRACKETS:
   - If `company_size` is missing or null in the live profile, seamlessly combine your empathy with a targeted bracket question.
   - Example: "...To help me gauge the operational scope of this scheduling issue, roughly how many total staff are we talking about across both locations: under 10, between 10 and 30, or over 50?"

3. EXPLORE BUSINESS FEAR / IMPACT:
   - Once team size and main pain point are captured, ask about the underlying strategic fear (e.g. risk of burnout, financial loss, service degradation).
"""

CALL_B_SYSTEM_PROMPT = """
You are a strict JSON data extraction engine updating the executive profile from full conversation history.

FULL-HISTORY EXTRACTION RULES:

1. DO NOT DROP PREVIOUSLY STATED PAIN POINTS:
   - Read the FULL conversation context. If the user stated "The problem is my kitchen staff, it's open bar on attendance", you MUST extract `primary_pain.value` = "Kitchen staff attendance and scheduling issues" with HIGH confidence (>=0.8), even if recent assistant questions focused on team size.

2. VAGUE VALUES INTERDICTION FOR FACTS:
   - DO NOT extract qualitative statements for `company_size` (e.g., "quite a lot of people", "many", "several").
   - Set `company_size.value` = null and `confidence` = 0.0 unless explicit numbers or numerical brackets are provided.

3. QUALITY OF EXECUTIVE FEAR CAPTURE:
   - DO NOT extract third-party quotes or anecdotes (e.g. "my parents said the restaurant industry is too hard") as executive fear.
   - Extract the active, personal business strain/concern felt by the prospect (e.g., "Personal & family strain due to operational overload", "Executive burnout risk").

4. STRICT USER CONFLICT DETECTION:
   - Only trigger `conflict_flag` = true if the USER explicitly contradicts a statement THEY previously made. Ignore AI assistant paraphrases.
"""

HUMAN_DIAGNOSIS_PROMPT = """
You are a trusted executive strategist writing directly to a CEO/Executive. 
Your tone must be warm, highly empathetic, direct, and pragmatic.

STRICT PRAGMATIC ACTION RULE:
- DO NOT recommend immediate software or workflow automation unless the root cause of the breakdown has already been diagnosed.
- If data or operational breakdowns are present, your "Immediate High-Impact Action" MUST be an **AUDIT & ROOT-CAUSE ANALYSIS** first.

FORMATTING:
- Use clear headings, short paragraphs, and bold key phrases for quick scanning.

Structure your report as follows:
1. 💡 **The Reality Check**: Acknowledge their exact situation directly, referencing their company size, tech stack, operational pain, and strategic risk.
2. 🚀 **Immediate High-Impact Action**: Recommend a pragmatic, low-overhead FIRST STEP.
3. 🛡️ **Leadership Direction**: Reassure the executive on how to realign focus and navigate strategic priorities.
"""

# -----------------------------------------------------------------------------
# 4. HELPERS: POST-PROCESSING, LOCAL & WEBHOOK STORAGE
# -----------------------------------------------------------------------------
def sanitize_email(email: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', email.strip().lower())

def enforce_conflict_flags(profile_dict: dict) -> dict:
    """
    DETERMINISTIC POST-PROCESSING:
    1. Filter out vague values for company_size.
    2. Enforce logic consistency.
    """
    facts = profile_dict.get("facts", {})
    comp_size = facts.get("company_size", {})
    val_size = str(comp_size.get("value", "")).lower()
    
    # Reject vague company size expressions
    vague_phrases = ["quite a lot", "a lot", "many people", "a bunch", "several", "quite a lot of people"]
    if any(phrase in val_size for phrase in vague_phrases):
        comp_size["value"] = None
        comp_size["confidence"] = 0.0

    # Strict conflict check across groups
    for group_key in ["facts", "interpretation"]:
        group = profile_dict.get(group_key, {})
        for attr_key, attr in group.items():
            if isinstance(attr, dict):
                val = attr.get("value")
                old_val = attr.get("old_value")
                
                if old_val and isinstance(old_val, str) and old_val.strip() and old_val != val:
                    attr["conflict_flag"] = True
                else:
                    attr["conflict_flag"] = False
                    
    return profile_dict

def save_and_sync_data(email: str, profile_data: dict, messages: list):
    if not email:
        return
    
    payload = {
        "user_email": email,
        "profile": profile_data,
        "chat_history": messages
    }
    
    safe_name = sanitize_email(email)
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            print(f"Webhook error: {e}")

def load_user_data(email: str):
    safe_name = sanitize_email(email)
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def check_gatekeeper_unlocked(profile: dict) -> bool:
    facts = profile.get("facts", {})
    interp = profile.get("interpretation", {})
    
    has_size = bool(facts.get("company_size", {}).get("value"))
    has_tools = bool(facts.get("tools", {}).get("value"))
    has_pain = bool(interp.get("primary_pain", {}).get("value"))
    has_fear = bool(interp.get("fear", {}).get("value"))
    
    return has_size and has_tools and has_pain and has_fear

# -----------------------------------------------------------------------------
# 5. HEADER & USER IDENTIFICATION
# -----------------------------------------------------------------------------
st.markdown("---")
user_email = st.text_input("📧 Enter your business email to start or restore your session:", key="email_input")

if "current_user" not in st.session_state:
    st.session_state.current_user = ""

if user_email and user_email != st.session_state.current_user:
    st.session_state.current_user = user_email
    existing_data = load_user_data(user_email)
    
    if existing_data:
        st.session_state.profile = enforce_conflict_flags(existing_data.get("profile", ExecutiveProfile().model_dump()))
        st.session_state.messages = existing_data.get("chat_history", [])
        st.success(f"Welcome back! Loaded saved profile for {user_email}")
    else:
        st.session_state.profile = ExecutiveProfile().model_dump()
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Welcome! I'm your strategic AI companion. To start, could you share your executive role and the industry you're operating in?"
            }
        ]
        save_and_sync_data(user_email, st.session_state.profile, st.session_state.messages)

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
# 6. LAYOUT: TWO COLUMNS
# -----------------------------------------------------------------------------
col_chat, col_profile = st.columns([3, 2])

# --- LEFT COLUMN: CHAT INTERFACE ---
with col_chat:
    st.subheader("💬 Executive Consultation")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("Type your message here...", disabled=not user_email):
        if not user_email:
            st.warning("Please enter your email above before starting the consultation.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.chat_message("user"):
                st.markdown(user_input)

            # 1. Extraction Call B
            try:
                conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
                res_B = client.beta.chat.completions.parse(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": CALL_B_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Previous State Profile JSON:\n{json.dumps(st.session_state.profile)}\n\nFull Conversation History:\n{conv_text}"}
                    ],
                    response_format=ExecutiveProfile,
                    temperature=0.0
                )
                raw_profile_dict = res_B.choices[0].message.parsed.model_dump()
                
                # ENFORCE DETERMINISTIC RULES IN PYTHON
                st.session_state.profile = enforce_conflict_flags(raw_profile_dict)

            except Exception as e:
                st.error(f"Extraction error: {e}")

            # 2. Dynamic Gatekeeper Status Check
            gatekeeper_is_unlocked = check_gatekeeper_unlocked(st.session_state.profile)
            gatekeeper_status_str = "UNLOCKED" if gatekeeper_is_unlocked else "LOCKED"

            # 3. Call A Generation
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    current_profile_str = json.dumps(st.session_state.profile)
                    
                    system_instruction = (
                        f"{CALL_A_SYSTEM_PROMPT}\n\n"
                        f"CURRENT LIVE PROFILE STATE:\n{current_profile_str}\n\n"
                        f"GATEKEEPER STATUS: {gatekeeper_status_str}\n"
                    )

                    res_A = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": system_instruction}, *st.session_state.messages],
                        temperature=0.7
                    )
                    reply = res_A.choices[0].message.content

                    # SOFT GUARD FALLBACK FOR COMPANY SIZE BRACKETS
                    facts = st.session_state.profile.get("facts", {})
                    has_size = bool(facts.get("company_size", {}).get("value"))
                    
                    if not has_size and not any(char.isdigit() for char in reply):
                        # Append brackets gracefully without wiping out Call A's empathetic response
                        reply += "\n\n*(Just to give us a clear baseline: are we talking under 10 total team members, between 10 and 30, or 50+ across both locations?)*"

                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

            # Save & Refresh
            save_and_sync_data(st.session_state.current_user, st.session_state.profile, st.session_state.messages)
            st.rerun()

# --- RIGHT COLUMN: VISUAL DASHBOARD ---
with col_profile:
    st.subheader("📊 Strategic Live Profile")

    p = st.session_state.profile
    facts = p.get("facts", {})
    interp = p.get("interpretation", {})

    def render_card(label, item):
        val = item.get("value")
        conflict = item.get("conflict_flag", False)
        old_val = item.get("old_value")

        if conflict:
            st.warning(f"**{label}:** {val}\n\n⚠️ *Contradiction detected — Previously stated:* `{old_val}`")
        elif val and val != "Not specified yet":
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

    # Gatekeeper status check
    unlocked = check_gatekeeper_unlocked(p)

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

    # BLOCK DEBUG JSON
    with st.expander("🛠️ Raw JSON State (Debug Mode)"):
        st.json(p)
