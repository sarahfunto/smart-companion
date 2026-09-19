import json
import os
import re
import base64
import tempfile
import requests  # (Optional: Webhook Make / Zapier)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
from pydantic import BaseModel, Field
from typing import Optional
from fpdf import FPDF

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DIRECTORY SETUP
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Smart Companion - Executive Profiler",
    page_icon="🎙️",
    layout="wide"
)

st.title("🎙️ Smart Companion - Voice & Executive Diagnostic")
st.caption("AI-Powered Executive Profiling with Voice Assistant & Interactive Analytics")

DATA_DIR = "saved_profiles"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("Please configure your OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=api_key)
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
    direct_team_size: ProfileAttribute = Field(default_factory=ProfileAttribute)
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

CRITICAL RULE WHEN GATEKEEPER IS UNLOCKED:
- IF `GATEKEEPER STATUS` is "UNLOCKED":
  STOP asking mandatory diagnostic questions.
  Directly inform the executive:
  "The diagnostic is now ready! I invite you to click the 'Generate Human Diagnostic Report' button on the right to review your tailored strategy. However, if any point feels unclear or if you would like to add more precision to any section, please feel free to share it with me and I will refine the analysis."

IF GATEKEEPER IS LOCKED (PRIORITY MATRIX & STEP-BY-STEP FLOW):
1. STEP 1 - MISSING FACTS (HIGHEST PRIORITY):
   - `company_size` & `direct_team_size`: Clarify overall company size vs immediate direct team scope.
   - `tools`: If vague (e.g., "standard tools"), ask for specific daily software/apps (e.g., Excel, WhatsApp, CRM).
   - `industry`: If missing/null, ask smoothly about their business domain/industry.

2. STEP 2 - STRATEGIC PAIN & FEARS:
   - Once basic facts are captured, ask about operational bottlenecks (`primary_pain`) and strategic impacts (`fear`/business risk).

3. EMPATHY & CLARITY RULE:
   - Acknowledge their previous response in ONE empathetic sentence before introducing your targeted question.
"""

CALL_B_SYSTEM_PROMPT = """
You are a strict JSON data extraction engine updating the executive profile from full conversation history.

SCOPE HANDLING & DUAL GRANULARITY RULES:
1. SEPARATE DIRECT TEAM VS COMPANY SIZE:
   - If the user distinguishes their immediate direct team size (e.g., "my direct team is 5") from the overall organization (e.g., "the whole company is around 150"), extract BOTH:
     * `direct_team_size.value` = "5 people"
     * `company_size.value` = "150 people"
   - Do NOT overwrite one with the other.

2. CLARIFICATION vs CONFLICT:
   - Refinement of a vague answer IS NOT A CONFLICT. Set `conflict_flag` = false and `old_value` = null when a user clarifies details.
   - Trigger `conflict_flag` = true ONLY if the user directly CONTRADICTS a clear, specific numerical or factual statement previously made.

3. TOOLS & FACTS EXTRACTION:
   - When tool names (Excel, WhatsApp, SAP, CRM, etc.) are present in the evidence, you MUST populate `tools.value` with the exact tool names and set confidence = 1.0.
   - DO NOT extract vague statements like "standard tools". Set value = null and confidence = 0.0 until specific facts are provided.

4. PAIN & FEAR EXTRACTION:
   - If user mentions margin decline, operational delays, inefficiency, or bottlenecks, extract into `primary_pain.value`.
   - If user mentions market share loss, competitors, bankruptcy, or failure, extract into `fear.value`.
"""

HUMAN_DIAGNOSIS_PROMPT = """
You are a trusted executive strategist writing directly to a CEO/Executive. 
Your tone must be warm, highly empathetic, direct, and pragmatic.

STRICT PRAGMATIC ACTION RULE:
- Focus on immediate high-impact value. Provide 3 concrete, short-term actions to execute within 3 days.
- DO NOT recommend immediate software or workflow automation unless the root cause of the breakdown has already been diagnosed.

FORMATTING:
- Use clear headings, short paragraphs, and bold key phrases for quick scanning.

Structure your report as follows:
1. 💡 **The Reality Check**: Acknowledge their exact situation directly, referencing their direct team size, overall company size, tech stack, operational pain, and strategic risk.
2. 🚀 **Immediate High-Impact Action (3-Day Execution Plan)**: Recommend 3 pragmatic, low-overhead FIRST STEPS.
3. 🛡️ **Leadership Direction**: Reassure the executive on how to realign focus and navigate strategic priorities.
"""

# -----------------------------------------------------------------------------
# 4. HELPERS & PDF GENERATOR
# -----------------------------------------------------------------------------
def sanitize_email(email: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', email.strip().lower())

def transcribe_audio(audio_bytes) -> str:
    """Robust audio transcription handling temporary file creation and cleanup."""
    tmp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_file_path = tmp_file.name

        with open(tmp_file_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        return transcript.text
    except Exception as e:
        st.error(f"Voice Transcription Error: {e}")
        return ""
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception:
                pass

def play_audio_response(text: str):
    """Generates OpenAI TTS speech and forces HTML5 autoplay."""
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text
        )
        audio_bytes = response.content
        b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        audio_html = f"""
            <audio autoplay controls style="width: 100%; margin-top: 10px;">
                <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
                Your browser does not support audio playback.
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Unable to generate speech: {e}")

def enforce_conflict_flags(profile_dict: dict) -> dict:
    facts = profile_dict.get("facts", {})
    comp_size = facts.get("company_size", {})
    val_size = str(comp_size.get("value", "")).lower()
    vague_size_phrases = ["decent size", "quite a lot", "a lot", "many people", "a bunch", "several"]
    if any(phrase in val_size for phrase in vague_size_phrases):
        comp_size["value"] = None
        comp_size["confidence"] = 0.0

    tools_item = facts.get("tools", {})
    val_tools = str(tools_item.get("value", "")).lower()
    vague_tools_phrases = ["standard tools", "nothing special", "usual stuff", "basic tools"]
    if any(phrase in val_tools for phrase in vague_tools_phrases):
        tools_item["value"] = None
        tools_item["confidence"] = 0.0

    for group_key in ["facts", "interpretation"]:
        group = profile_dict.get(group_key, {})
        for attr_key, attr in group.items():
            if isinstance(attr, dict):
                val = attr.get("value")
                old_val = attr.get("old_value")
                if old_val and isinstance(old_val, str):
                    old_clean = old_val.lower().strip()
                    if any(v in old_clean for v in vague_tools_phrases + vague_size_phrases):
                        attr["conflict_flag"] = False
                        attr["old_value"] = None
                    elif old_val != val and val is not None:
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
    has_size = bool(facts.get("company_size", {}).get("value")) or bool(facts.get("direct_team_size", {}).get("value"))
    has_tools = bool(facts.get("tools", {}).get("value"))
    has_pain = bool(interp.get("primary_pain", {}).get("value"))
    has_fear = bool(interp.get("fear", {}).get("value"))
    return has_size and has_tools and has_pain and has_fear

def calculate_progress(profile: dict) -> float:
    facts = profile.get("facts", {})
    interp = profile.get("interpretation", {})
    total_slots = 5
    filled_slots = 0
    if facts.get("industry", {}).get("value"): filled_slots += 1
    if facts.get("company_size", {}).get("value") or facts.get("direct_team_size", {}).get("value"): filled_slots += 1
    if facts.get("tools", {}).get("value"): filled_slots += 1
    if interp.get("primary_pain", {}).get("value"): filled_slots += 1
    if interp.get("fear", {}).get("value"): filled_slots += 1
    return filled_slots / total_slots

def parse_number(val_str: Optional[str]) -> int:
    """Helper to extract numbers from strings like '50 employees' -> 50."""
    if not val_str:
        return 0
    nums = re.findall(r'\d+', str(val_str))
    return int(nums[0]) if nums else 0

def generate_pdf_report(profile: dict, report_text: str) -> bytes:
    """Generates a clean PDF version of the Executive Diagnostic."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=16, style="B")
    pdf.cell(0, 10, text="Smart Companion - Executive Diagnostic Report", new_x="LMARGIN", new_y="NEXT", align="C")
    
    pdf.set_font("Helvetica", size=10, style="I")
    pdf.cell(0, 8, text="Generated automatically from your executive consultation session", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)

    # Key Facts Section
    pdf.set_font("Helvetica", size=12, style="B")
    pdf.cell(0, 8, text="1. Profile Context & Key Facts", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    
    facts = profile.get("facts", {})
    interp = profile.get("interpretation", {})
    
    pdf.cell(0, 6, text=f"- Industry: {facts.get('industry', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=f"- Direct Team Size: {facts.get('direct_team_size', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=f"- Overall Company Size: {facts.get('company_size', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=f"- Current Tech Stack / Tools: {facts.get('tools', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=f"- Primary Bottleneck: {interp.get('primary_pain', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=f"- Critical Risk / Concern: {interp.get('fear', {}).get('value', 'N/A')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Diagnostic Body
    pdf.set_font("Helvetica", size=12, style="B")
    pdf.cell(0, 8, text="2. Strategic Diagnostic & Action Plan", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    
    # Strip markdown bolding for PDF
    clean_text = report_text.replace("**", "").replace("#", "")
    pdf.multi_cell(0, 6, text=clean_text)
    
    return bytes(pdf.output())

# -----------------------------------------------------------------------------
# 5. HEADER & USER IDENTIFICATION
# -----------------------------------------------------------------------------
st.markdown("---")
user_email = st.text_input("📧 Enter your business email to start or restore your session:", key="email_input")

if "current_user" not in st.session_state:
    st.session_state.current_user = ""

if "last_processed_audio" not in st.session_state:
    st.session_state.last_processed_audio = None

if "last_reply_text" not in st.session_state:
    st.session_state.last_reply_text = None

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

# --- LEFT COLUMN: CHAT & VOICE INTERFACE ---
with col_chat:
    st.subheader("💬 Executive Consultation (Voice & Text)")
    
    progress_val = calculate_progress(st.session_state.profile)
    st.progress(progress_val, text=f"Diagnostic Readiness: {int(progress_val * 100)}%")

    # Display chat history
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and idx == len(st.session_state.messages) - 1 and st.session_state.last_reply_text:
                play_audio_response(st.session_state.last_reply_text)

    user_input = None

    audio_value = st.audio_input("🎙️ Speak to your AI Companion", disabled=not user_email, key="voice_input")
    if audio_value:
        audio_bytes = audio_value.read()
        if audio_bytes != st.session_state.last_processed_audio:
            with st.spinner("Transcribing voice input..."):
                user_input = transcribe_audio(audio_bytes)
                st.session_state.last_processed_audio = audio_bytes

    text_val = st.chat_input("Or type your message here...", disabled=not user_email)
    if text_val and not user_input:
        user_input = text_val

    if user_input and user_email:
        st.session_state.messages.append({"role": "user", "content": user_input})

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
            st.session_state.profile = enforce_conflict_flags(raw_profile_dict)
        except Exception as e:
            st.error(f"Extraction error: {e}")

        # 2. Call A Response
        gatekeeper_is_unlocked = check_gatekeeper_unlocked(st.session_state.profile)
        gatekeeper_status_str = "UNLOCKED" if gatekeeper_is_unlocked else "LOCKED"

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

            st.session_state.messages.append({
                "role": "assistant", 
                "content": reply
            })
            st.session_state.last_reply_text = reply

        save_and_sync_data(st.session_state.current_user, st.session_state.profile, st.session_state.messages)
        st.rerun()

# --- RIGHT COLUMN: VISUAL DASHBOARD & DYNAMIC REPORTS ---
with col_profile:
    st.subheader("📊 Strategic Live Profile")

    p = st.session_state.profile
    facts = p.get("facts", {})
    interp = p.get("interpretation", {})

    tab_overview, tab_analytics = st.tabs(["📋 Executive Summary", "📈 Analytics & Diagrams"])

    with tab_overview:
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
        render_card("Direct Team Size", facts.get("direct_team_size", {}))
        render_card("Company Size (Overall)", facts.get("company_size", {}))
        render_card("Current Tools", facts.get("tools", {}))

        st.markdown("### 🎯 Strategic Insights")
        render_card("Primary Pain Point", interp.get("primary_pain", {}))
        render_card("Market Trigger", interp.get("trigger", {}))
        render_card("Executive Fear / Concern", interp.get("fear", {}))

    with tab_analytics:
        st.markdown("### 📊 Operational Scope Breakdown")
        
        direct_n = parse_number(facts.get("direct_team_size", {}).get("value"))
        total_n = parse_number(facts.get("company_size", {}).get("value"))

        if total_n > 0 or direct_n > 0:
            df_chart = pd.DataFrame({
                "Scope": ["Direct Team", "Remaining Company"],
                "Headcount": [direct_n, max(0, total_n - direct_n)]
            })
            fig = px.bar(df_chart, x="Scope", y="Headcount", color="Scope", title="Team vs Company Scale", text_auto=True)
            fig.update_layout(showlegend=False, height=280)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("Provide numeric team & company sizes to render headcount chart.")

        st.markdown("### 🎯 Strategic Radar")
        categories = ['Operational Clarity', 'Tool Alignment', 'Risk Mitigation', 'Strategic Focus']
        
        # Calculate score based on extracted metrics
        score_clarity = 80 if facts.get("industry", {}).get("value") else 30
        score_tools = 80 if facts.get("tools", {}).get("value") else 20
        score_risk = 40 if interp.get("fear", {}).get("value") else 80
        score_focus = 40 if interp.get("primary_pain", {}).get("value") else 80

        fig_radar = go.Figure(data=go.Scatterpolar(
            r=[score_clarity, score_tools, score_risk, score_focus],
            theta=categories,
            fill='toself'
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            height=300
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    st.divider()

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
            st.session_state.current_report = diag_res.choices[0].message.content

    if "current_report" in st.session_state:
        st.markdown("---")
        st.markdown(st.session_state.current_report)

        pdf_bytes = generate_pdf_report(p, st.session_state.current_report)
        st.download_button(
            label="📥 Download Executive Diagnostic (PDF)",
            data=pdf_bytes,
            file_name="Executive_Diagnostic_Report.pdf",
            mime="application/pdf"
        )

    with st.expander("🛠️ Raw JSON State (Debug Mode)"):
        st.json(p)
