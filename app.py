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
# 3. SYSTEM PROMPTS (FIXED: STRICT DRILL-DOWN & RECENT FACT OVERRIDE)
# -----------------------------------------------------------------------------
CALL_A_SYSTEM_PROMPT = """
You are a warm, highly empathetic senior AI strategy consultant speaking directly to an executive.

YOUR GOAL:
Guide the executive step-by-step to understand their situation. Always validate their pressure or emotion before asking a question.

CRITICAL RULE: MANDATORY INTERACTION STOPPER FOR VAGUE INPUTS
When the executive gives an imprecise or vague answer, YOU MUST NOT CONTINUE THE REGULAR CONSULTATION FLOW.
You MUST IMMEDIATELY ask a structured follow-up question offering 2 to 4 concrete choices.

EXACT PATTERNS TO INTERCEPT:
1. Vague Size ('decent-sized business', 'around a hundred people, maybe a bit more'):
   --> STOP and ASK: "To make sure I capture the company size correctly, would you say you're closer to 100, 120, or more than 150 employees?"
2. Vague Tools ('classic stuff everyone uses', 'standard tools', 'usual software'):
   --> STOP and ASK: "When you say classic tools, do you mean mainly Excel, an ERP such as Sage or SAP, email, or something else?"
3. Vague Pain ('reporting is annoying', 'too many manual tasks'):
   --> STOP and ASK: "To narrow this down: is the issue manual data consolidation across spreadsheets, delay in getting data from team leaders, or lack of real-time reporting?"

SPECIAL CASES:
1. IF THE EXECUTIVE HAS NO TIME / REFUSES QUESTIONS / DEMANDS A QUICK YES/NO:
   - Provide a concise, direct answer. Do NOT ask further diagnostic questions.
   - Conclude warmly with a sign-off.

2. IF THE DIAGNOSTIC PROFILE IS COMPLETE (Industry, Exact Size, Specific Tools, and Specific Primary Pain are fully known):
   - Inform them warmly: "Thank you for sharing these details! I have gathered all key insights needed. You can now click on the **Generate Human Diagnostic Report** button on the right panel to view your customized strategic analysis."
"""

CALL_B_SYSTEM_PROMPT = """
You are an ultra-precise JSON extractor. Evaluate the full conversation and extract the final state into the structured schema.

CRITICAL EXTRACTION & OVERWRITE RULES:

1. RECENT SPECIFIC FACTS ALWAYS OVERRIDE PREVIOUS VAGUE STATEMENTS
- If the conversation starts with a vague term ('medium', 'decent-sized') but later the user confirms a number ('Yes, 120 is close enough'), YOU MUST SET company_size.value = 'approximately 120 employees'. (DO NOT LEAVE IT AS 'medium').
- If the conversation starts with 'classic tools' but later the user specifies 'Mainly Excel and Sage', YOU MUST SET tools.value = 'Excel, Sage'. (DO NOT LEAVE IT AS 'classic tools').
- If the pain transitions from 'reporting is annoying' to 'Every month we manually combine financial reports from several Excel files', YOU MUST SET primary_pain.value = 'Manual consolidation of financial reports from several Excel files'.

2. REACTION TO UNCONFIRMED VAGUE STATEMENTS
- If a category ONLY contains vague text and NO specific details have been provided yet in the entire conversation, set value = null (or leave empty). NEVER store 'medium' or 'classic tools' as final values.

3. CONFLICT FLAGS
- Refining a vague statement with precise data (e.g. medium -> 120 employees) is NOT a conflict. Keep conflict_flag = false.

4. MARKET TRIGGER
- MARKET TRIGGER ("trigger"): Populate ONLY if the user explicitly mentions EXTERNAL market forces outside their control. Internal operational issues are NOT market triggers (set value = null if not stated).
"""

HUMAN_DIAGNOSIS_PROMPT = """
You are a trusted executive strategist writing directly to a CEO/Executive. 
Your tone must be warm, highly empathetic, direct, and pragmatic.

STRICT BOTTLENECK ALIGNMENT & ACCURACY RULE:
- Focus ONLY on the primary_pain specified in the profile.
- IF primary_pain mentions a specific operational breakdown (e.g., manual Excel consolidation for financial reports), your "Immediate High-Impact Action" MUST directly target that exact process using their exact stated tools (e.g., Sage, Excel).
- Avoid generic, fluffy recommendations like "hold a morning triage meeting" when a concrete workflow bottleneck has been identified.

FORMATTING:
- Use clear headings, short paragraphs, and bold key phrases for quick scanning.

Structure your report as follows:
1. 💡 **The Reality Check**: Acknowledge their exact situation directly, referencing their exact team size, precise tools (e.g., Sage, Excel), and the primary operational breakdown.
2. 🚀 **Immediate High-Impact Action**: Provide ONE pragmatic action step targeting the exact process friction using minimal technical overhead (e.g., automated consolidation between Sage and Excel).
3. 🛡️ **Leadership Direction**: Provide calm strategic reassurance on how to streamline financial workflows while keeping team operations smooth.
"""

# -----------------------------------------------------------------------------
# 4. HELPERS: LOCAL & WEBHOOK STORAGE
# -----------------------------------------------------------------------------
def sanitize_email(email: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', email.strip().lower())

def save_and_sync_data(email: str, profile_data: dict, messages: list):
    if not email:
        return
    
    payload = {
        "user_email": email,
        "profile": profile_data,
        "chat_history": messages
    }
    
    # 1. Local backup on server
    safe_name = sanitize_email(email)
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        
    # 2. Sync to Webhook for Google Sheets / Make
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
        st.session_state.profile = existing_data.get("profile", ExecutiveProfile().model_dump())
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

            # Call A Execution
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    current_profile_str = json.dumps(st.session_state.profile)
                    system_with_context = f"{CALL_A_SYSTEM_PROMPT}\n\nCurrent Extracted Profile Context:\n{current_profile_str}"
                    
                    res_A = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": system_with_context}, *st.session_state.messages],
                        temperature=0.7
                    )
                    reply = res_A.choices[0].message.content
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

            # Call B Extraction & Webhook Sync (Full Conv History Focus)
            try:
                conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
                res_B = client.beta.chat.completions.parse(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": CALL_B_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Full Conversation History:\n{conv_text}"}
                    ],
                    response_format=ExecutiveProfile,
                    temperature=0.0
                )
                st.session_state.profile = res_B.choices[0].message.parsed.model_dump()
                
                # Sync local + Webhook
                save_and_sync_data(st.session_state.current_user, st.session_state.profile, st.session_state.messages)
                st.rerun()
            except Exception as e:
                st.error(f"Extraction error: {e}")

# --- RIGHT COLUMN: VISUAL DASHBOARD ---
with col_profile:
    st.subheader("📊 Strategic Live Profile")

    p = st.session_state.profile
    facts = p.get("facts", {})
    interp = p.get("interpretation", {})

    def render_card(label, item):
        val = item.get("value")
        conflict = item.get("conflict_flag", False)

        if conflict:
            st.warning(f"**{label}:** {val} *(⚠️ Changed from: {item.get('old_value')})*")
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

    # Gatekeeper Validation Logic
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
