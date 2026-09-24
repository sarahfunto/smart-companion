import json
import os
import re
import base64
import tempfile
import streamlit as st
import streamlit.components.v1 as components
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
st.caption("AI-Powered Executive Profiling with WebRTC Voice Control & Dynamic Flow")

DATA_DIR = "saved_profiles"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

api_key = st.secrets.get("OPENAI_API_KEY")
if not api_key:
    st.error("Please configure your OPENAI_API_KEY in .streamlit/secrets.toml")
    st.stop()

client = OpenAI(api_key=api_key)

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

STRICT MANDATE ON REPHRASING & SEQUENTIAL PROGRESSION:
You must strictly obtain valid factual information for the current active step before moving forward.

RULE FOR OFF-TOPIC, VAGUE, OR CASUAL INPUTS (e.g., "hi", "coucou", "ok", "I don't know"):
1. ACKNOWLEDGE & REFRAME: Warmly acknowledge their response and adapt to their tone.
2. REPHRASE THE CURRENT QUESTION: Rephrase the current missing question in a fresh, engaging, or simpler way.
3. ABSOLUTE BLOCK: DO NOT move to the next topic until the current step's required field is populated in the profile state.

SEQUENTIAL FLOW:
- STEP 1 (Role & Industry):
  Condition: Is `industry.value` filled?
  If NO -> Acknowledge, REPHRASE and re-ask about their executive role and industry sector. DO NOT ask about team size or tools yet.

- STEP 2 (Direct Team vs Company Scope):
  Condition: Is `direct_team_size.value` or `company_size.value` filled?
  If NO -> Acknowledge, REPHRASE and ask specifically to clarify direct team size versus overall company scale.

- STEP 3 (Current Tech Stack / Tools):
  Condition: Is `tools.value` filled?
  If NO -> Acknowledge, REPHRASE and ask about the specific software and platforms used daily.

- STEP 4 (Bottlenecks & Critical Concerns):
  Condition: Are `primary_pain.value` and `fear.value` filled?
  If NO -> Acknowledge, REPHRASE and ask about operational delays or strategic fears.

GATEKEEPER UNLOCKED RULE:
- IF `GATEKEEPER STATUS` is "UNLOCKED":
  Directly inform the executive:
  "The diagnostic is now complete and ready! I invite you to click the 'Generate Human Diagnostic Report' button on the right sidebar to review your tailored strategy. However, if any point feels unclear or if you would like to add more precision or additional context to any section, please feel free to share it with me here, and I will continuously refine and optimize the analysis for you."
"""

CALL_B_SYSTEM_PROMPT = """
You are a strict JSON data extraction engine updating the executive profile from full conversation history.

EXTRACTION RULES:
1. SEPARATE SCOPES: Extract `direct_team_size` separately from `company_size`.
2. CLARIFICATION HANDLING: Refinement of vague input is NOT a conflict. Set `conflict_flag` = true ONLY for direct contradictions.
3. TOOLS: Extract explicit software and tool names. Ignore generic terms like "usual tools".
4. PAINS & RISKS: Extract clear operational bottlenecks into `primary_pain` and key business fears into `fear`.
"""

HUMAN_DIAGNOSIS_PROMPT = """
You are a trusted executive strategist writing directly to a CEO/Executive. 
Your tone must be warm, highly empathetic, direct, and pragmatic.
Provide 3 concrete, short-term actions to execute within 3 days.

Structure your report as follows:
1. The Reality Check: Acknowledge their exact situation directly, referencing team scale, tools, and main risks.
2. Immediate High-Impact Action (3-Day Execution Plan): Recommend 3 pragmatic, low-overhead first steps.
3. Leadership Direction: Reassure the executive on how to realign focus.
"""

# -----------------------------------------------------------------------------
# 4. HELPERS & PDF GENERATOR
# -----------------------------------------------------------------------------
def sanitize_email(email: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', email.strip().lower())

def transcribe_audio(audio_bytes) -> str:
    if not audio_bytes or len(audio_bytes) < 1000:
        return ""
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
        return transcript.text.strip()
    except Exception as e:
        st.warning(f"Voice transcription error: {e}")
        return ""
    finally:
        if tmp_file_path and os.path.exists(tmp_file_path):
            try:
                os.remove(tmp_file_path)
            except Exception:
                pass

def play_audio_response(text: str):
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
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception:
        pass

def clean_text_for_pdf(text: str) -> str:
    if not text:
        return ""
    text = text.replace("**", "").replace("#", "").replace("•", "-")
    return text.encode('latin-1', 'ignore').decode('latin-1')

def generate_pdf_report(profile: dict, report_text: str, fig_bar: go.Figure = None, fig_radar: go.Figure = None) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    PRIMARY = (31, 78, 121)
    TEXT_COLOR = (40, 40, 40)
    
    pdf.set_font("Helvetica", size=18, style="B")
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 10, text="Executive Diagnostic Report", new_x="LMARGIN", new_y="NEXT", align="L")
    pdf.ln(4)

    facts = profile.get("facts", {})
    interp = profile.get("interpretation", {})

    pdf.set_font("Helvetica", size=12, style="B")
    pdf.cell(0, 8, text="1. Profile Context & Scope", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, text=clean_text_for_pdf(f"Industry: {facts.get('industry', {}).get('value', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=clean_text_for_pdf(f"Direct Team: {facts.get('direct_team_size', {}).get('value', 'N/A')} | Company Size: {facts.get('company_size', {}).get('value', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, text=clean_text_for_pdf(f"Tech Stack: {facts.get('tools', {}).get('value', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    tmp_files = []
    try:
        if fig_bar and fig_radar:
            tmp_bar = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_radar = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_files.extend([tmp_bar.name, tmp_radar.name])

            fig_bar.write_image(tmp_bar.name, format="png", width=500, height=300)
            fig_radar.write_image(tmp_radar.name, format="png", width=500, height=300)

            chart_y = pdf.get_y()
            pdf.image(tmp_bar.name, x=10, y=chart_y, w=90)
            pdf.image(tmp_radar.name, x=105, y=chart_y, w=90)
            pdf.set_y(chart_y + 55)
    except Exception:
        pass
    finally:
        for tmp_path in tmp_files:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    pdf.ln(4)
    pdf.set_font("Helvetica", size=12, style="B")
    pdf.set_text_color(*PRIMARY)
    pdf.cell(0, 8, text="2. Strategic Diagnostic & Action Plan", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(*TEXT_COLOR)
    
    pdf.multi_cell(0, 5, text=clean_text_for_pdf(report_text), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())

def save_and_sync_data(email: str, profile_data: dict, messages: list):
    if not email:
        return
    payload = {"user_email": email, "profile": profile_data, "chat_history": messages}
    safe_name = sanitize_email(email)
    path = os.path.join(DATA_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

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
    total = 5
    cnt = 0
    if facts.get("industry", {}).get("value"): cnt += 1
    if facts.get("company_size", {}).get("value") or facts.get("direct_team_size", {}).get("value"): cnt += 1
    if facts.get("tools", {}).get("value"): cnt += 1
    if interp.get("primary_pain", {}).get("value"): cnt += 1
    if interp.get("fear", {}).get("value"): cnt += 1
    return cnt / total

def parse_number(val_str: Optional[str]) -> int:
    if not val_str:
        return 0
    nums = re.findall(r'\d+', str(val_str))
    return int(nums[0]) if nums else 0

# -----------------------------------------------------------------------------
# 5. SESSION INITIALIZATION
# -----------------------------------------------------------------------------
user_email = st.text_input("📧 Enter your business email to start or restore your session:", key="email_input")

if "current_user" not in st.session_state:
    st.session_state.current_user = ""

if "last_reply_text" not in st.session_state:
    st.session_state.last_reply_text = None

if user_email and user_email != st.session_state.current_user:
    st.session_state.current_user = user_email
    existing_data = load_user_data(user_email)
    if existing_data:
        st.session_state.profile = existing_data.get("profile", ExecutiveProfile().model_dump())
        st.session_state.messages = existing_data.get("chat_history", [])
    else:
        st.session_state.profile = ExecutiveProfile().model_dump()
        st.session_state.messages = [{
            "role": "assistant",
            "content": "Welcome! I am your strategic AI companion. To begin, could you please share your executive role and the industry sector you operate in?"
        }]
        save_and_sync_data(user_email, st.session_state.profile, st.session_state.messages)

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Welcome! I am your strategic AI companion. To begin, could you please share your executive role and the industry sector you operate in?"
    }]

if "profile" not in st.session_state:
    st.session_state.profile = ExecutiveProfile().model_dump()

# -----------------------------------------------------------------------------
# 6. LAYOUT & INTERFACE
# -----------------------------------------------------------------------------
col_chat, col_profile = st.columns([3, 2])

# --- LEFT COLUMN: CONSULTATION CHAT ---
with col_chat:
    st.subheader("💬 Executive Consultation (Voice & Text)")
    
    progress_val = calculate_progress(st.session_state.profile)
    st.progress(progress_val, text=f"Diagnostic Readiness: {int(progress_val * 100)}%")

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and idx == len(st.session_state.messages) - 1 and st.session_state.last_reply_text:
                play_audio_response(st.session_state.last_reply_text)

    user_input = None

    # --- WEBRTC JS VOICE BUTTONS (START / STOP) ---
    st.markdown("#### 🎙️ Voice Control Panel")
    
    js_recorder_code = """
    <div style="font-family: sans-serif; display: flex; gap: 10px; align-items: center; margin-bottom: 10px;">
        <button id="startBtn" onclick="startRecording()" style="padding: 10px 16px; background-color: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold;">
            ▶️ Start Speaking
        </button>
        <button id="stopBtn" onclick="stopRecording()" disabled style="padding: 10px 16px; background-color: #dc3545; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; opacity: 0.5;">
            ⏹️ Stop & Send
        </button>
        <span id="status" style="font-size: 14px; color: #555;">Ready</span>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];

        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const reader = new FileReader();
                    reader.readAsDataURL(audioBlob);
                    reader.onloadend = () => {
                        const base64Audio = reader.result.split(',')[1];
                        window.parent.postMessage({
                            type: 'streamlit:setComponentValue',
                            value: base64Audio
                        }, '*');
                    };
                };

                mediaRecorder.start();
                document.getElementById('startBtn').disabled = true;
                document.getElementById('startBtn').style.opacity = '0.5';
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('stopBtn').style.opacity = '1.0';
                document.getElementById('status').innerText = '🔴 Recording...';
            } catch (err) {
                document.getElementById('status').innerText = '⚠️ Microphone Access Denied';
            }
        }

        function stopRecording() {
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                document.getElementById('startBtn').disabled = false;
                document.getElementById('startBtn').style.opacity = '1.0';
                document.getElementById('stopBtn').disabled = true;
                document.getElementById('stopBtn').style.opacity = '0.5';
                document.getElementById('status').innerText = '⏳ Processing Audio...';
            }
        }
    </script>
    """
    
    voice_b64 = components.html(js_recorder_code, height=60)

    if voice_b64 and isinstance(voice_b64, str) and len(voice_b64) > 100:
        try:
            audio_bytes = base64.b64decode(voice_b64)
            transcribed = transcribe_audio(audio_bytes)
            if transcribed:
                user_input = transcribed
        except Exception:
            st.warning("Failed to process voice input.")

    text_val = st.chat_input("Or type your message here...", disabled=not user_email)
    if text_val and not user_input:
        user_input = text_val

    if user_input and user_email:
        st.session_state.messages.append({"role": "user", "content": user_input})

        try:
            conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
            res_B = client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": CALL_B_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Previous Profile:\n{json.dumps(st.session_state.profile)}\n\nHistory:\n{conv_text}"}
                ],
                response_format=ExecutiveProfile,
                temperature=0.0
            )
            st.session_state.profile = res_B.choices[0].message.parsed.model_dump()

            gatekeeper_unlocked = check_gatekeeper_unlocked(st.session_state.profile)
            status_str = "UNLOCKED" if gatekeeper_unlocked else "LOCKED"

            with st.spinner("Processing insights..."):
                sys_inst = f"{CALL_A_SYSTEM_PROMPT}\n\nPROFILE STATE:\n{json.dumps(st.session_state.profile)}\nGATEKEEPER STATUS: {status_str}"
                
                res_A = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "system", "content": sys_inst}, *st.session_state.messages],
                    temperature=0.7
                )
                reply = res_A.choices[0].message.content

                st.session_state.messages.append({"role": "assistant", "content": reply})
                st.session_state.last_reply_text = reply

            save_and_sync_data(st.session_state.current_user, st.session_state.profile, st.session_state.messages)
            st.rerun()

        except Exception as e:
            st.error(f"AI Processing Error: {e}")

# --- RIGHT COLUMN: DASHBOARD & REPORT GENERATION ---
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
        st.markdown("### 📊 Scope Scale Breakdown")
        direct_n = parse_number(facts.get("direct_team_size", {}).get("value"))
        total_n = parse_number(facts.get("company_size", {}).get("value"))

        df_chart = pd.DataFrame({
            "Scope": ["Direct Team", "Remaining Workforce"],
            "Headcount": [direct_n, max(0, total_n - direct_n)]
        })
        fig_bar = px.bar(df_chart, x="Scope", y="Headcount", color="Scope", title="Team Scope vs Company Scale", text_auto=True)
        fig_bar.update_layout(showlegend=False, height=280)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("### 🎯 Strategic Alignment Radar")
        categories = ['Operational Clarity', 'Tool Alignment', 'Risk Mitigation', 'Strategic Focus']
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
        with st.spinner("Generating executive report..."):
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

        try:
            pdf_bytes = generate_pdf_report(p, st.session_state.current_report, fig_bar=fig_bar, fig_radar=fig_radar)
            st.download_button(
                label="📥 Download Executive Diagnostic (PDF with Charts)",
                data=pdf_bytes,
                file_name="Executive_Diagnostic_Report.pdf",
                mime="application/pdf"
            )
        except Exception as e:
            st.error(f"PDF Generation Error: {e}")

    with st.expander("🛠️ Raw JSON State (Debug Mode)"):
        st.json(p)
