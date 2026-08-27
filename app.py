import streamlit as st
import json
import unicodedata
import difflib
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI

# ---------------------------------------------------------
# 1. OPENAI INITIALIZATION & CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="Smart Companion - CEO Interview", layout="wide")

if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY missing in Streamlit Secrets.")
    client = None

# ---------------------------------------------------------
# 2. STRICT PYDANTIC SCHEMA (Part 1 - Smart Companion Scheme)
# ---------------------------------------------------------
class FieldAttribute(BaseModel):
    value: Optional[Any] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = Field(default="inferred", description="stated | inferred | manual | external")
    evidence: Optional[str] = Field(default=None, description="Verbatim text quote")
    conflict_flag: bool = False
    old_value: Optional[Any] = None
    manual_locked: bool = False

class GroupAFacts(BaseModel):
    industry: FieldAttribute = Field(default_factory=FieldAttribute)
    company_size: FieldAttribute = Field(default_factory=FieldAttribute)
    speaker_role: FieldAttribute = Field(default_factory=FieldAttribute)
    tools: FieldAttribute = Field(default_factory=FieldAttribute)
    org_context: FieldAttribute = Field(default_factory=FieldAttribute)

class GroupBInterpretation(BaseModel):
    trigger: FieldAttribute = Field(default_factory=FieldAttribute)
    lens: FieldAttribute = Field(default_factory=FieldAttribute)
    primary_pain: FieldAttribute = Field(default_factory=FieldAttribute)
    fear: FieldAttribute = Field(default_factory=FieldAttribute)
    strategic_posture: FieldAttribute = Field(default_factory=FieldAttribute)
    value_discipline: FieldAttribute = Field(default_factory=FieldAttribute)
    surface_anchor: FieldAttribute = Field(default_factory=FieldAttribute)
    ai_maturity: FieldAttribute = Field(default_factory=FieldAttribute)
    objective: FieldAttribute = Field(default_factory=FieldAttribute)

class GroupCAbsence(BaseModel):
    inferred_insights: List[str] = []
    gaps: List[str] = []

class CEOProfile(BaseModel):
    facts: GroupAFacts = Field(default_factory=GroupAFacts)
    interpretation: GroupBInterpretation = Field(default_factory=GroupBInterpretation)
    absence: GroupCAbsence = Field(default_factory=GroupCAbsence)

# ---------------------------------------------------------
# 3. SESSION INITIALIZATION & RESET
# ---------------------------------------------------------
def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "profile" not in st.session_state:
        st.session_state.profile = CEOProfile().model_dump()
    if "last_changes" not in st.session_state:
        st.session_state.last_changes = []

def reset_session():
    st.session_state.messages = []
    st.session_state.profile = CEOProfile().model_dump()
    st.session_state.last_changes = []
    st.rerun()

init_session()

# ---------------------------------------------------------
# 4. EXECUTION LOOP ENGINE (Part 2 - Call A & Call B)
# ---------------------------------------------------------

# CALL A: Pure Conversational AI
def call_a_chat(user_message: str) -> str:
    conversation_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    conversation_history.append({"role": "user", "content": user_message})
    
    sys_prompt = "You are an expert AI Transformation Consultant. Conduct a fluid, highly professional, and empathetic interview with an executive CEO."
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": sys_prompt}] + conversation_history,
        temperature=0.7
    )
    return response.choices[0].message.content
# CALL B: Strict JSON Schema Extraction
EXTRACTION_PROMPT = """
You are a precision structural extractor. Your sole task is to analyze the latest CEO response turn and update the structured CEO JSON profile table.

STRICT EXTRACTION RULES:
1. MERGE PRINCIPLE: Keep existing field values from the Current Profile State UNLESS the user explicitly provides updated information or contradicts previous statements.
2. For EVERY extracted field under Group A and Group B, populate:
   - "value": Enforced enum or explicit extracted text.
   - "confidence": Floating numerical score from 0.0 to 1.0 (Set >= 0.8 if stated directly).
   - "source": Exactly "stated" (if explicitly declared) or "inferred" (if subtextual/deduced).
   - "evidence": Exact verbatim text anchor quoted from the user input. IF NO DIRECT QUOTE JUSTIFIES THE CLAIM, LEAVE FIELD EMPTY.
3. Group C:
   - "inferred_insights": Unstated insights supported by profile data (at least 1 insight required).
   - "gaps": List unstated elements (e.g. undisclosed maturity, fear, operational blockers).

REQUIRED ENUMS:
- industry: One of [Manufacturing, Logistics & Distribution, Retail & E-commerce, Professional Services, Healthcare, Construction & Real Estate, Food & Agriculture, SaaS/Software, Financial Services]
- trigger: One of [Competitive, Internal, External, Personal, Seasonal]
- lens: One of [Performance, People, Market, Control]
- fear: One of [wasted investment, loss of control, employee resistance, vendor distrust, looking foolish, exposure (unspoken), personal irrelevance (unspoken)]
- strategic_posture: One of [Prospector, Defender, Analyzer, Reactor]

Respond EXCLUSIVELY with a valid JSON matching the profile schema.
"""

def merge_extraction_into_profile(extracted: dict, raw_user_text: str):
    current = st.session_state.profile
    st.session_state.last_changes = []

    for group in ["facts", "interpretation"]:
        if group in extracted:
            for field, incoming_data in extracted[group].items():
                if field in current[group] and isinstance(incoming_data, dict):
                    target = current[group][field]
                    
                    # 1. Manual Lock Rule Enforcement
                    if target.get("manual_locked", False):
                        continue
                    
                    new_val = incoming_data.get("value")
                    new_conf = incoming_data.get("confidence", 0.0)
                    new_source = incoming_data.get("source", "inferred")
                    new_ev = incoming_data.get("evidence")

                    # Update if new information is provided
                    if new_val:
                        # 2. Conflict Rule Enforcement
                        if target.get("value") and str(target.get("value")).lower() != str(new_val).lower() and target.get("source") == "stated" and new_source == "stated":
                            target["conflict_flag"] = True
                            target["old_value"] = target.get("value")
                            target["value"] = new_val
                            target["evidence"] = new_ev or target.get("evidence")
                            st.session_state.last_changes.append(f"⚠️ CONFLICT ON {field}: '{target['old_value']}' vs '{new_val}'")
                        else:
                            target["value"] = new_val
                            target["confidence"] = max(new_conf, target.get("confidence", 0.0))
                            target["source"] = new_source
                            if new_ev:
                                target["evidence"] = new_ev
                            st.session_state.last_changes.append(f"✅ UPDATED {field} -> {new_val}")

    if "absence" in extracted:
        if extracted["absence"].get("inferred_insights"):
            current["absence"]["inferred_insights"] = extracted["absence"]["inferred_insights"]
        if extracted["absence"].get("gaps"):
            current["absence"]["gaps"] = extracted["absence"]["gaps"]

# ---------------------------------------------------------
# 5. CODE-BASED GATEKEEPER (Threshold Checks)
# ---------------------------------------------------------
def check_gate_thresholds(profile: dict):
    facts = profile["facts"]
    interp = profile["interpretation"]
    absence = profile["absence"]

    missing_basic = []
    if (facts["industry"].get("confidence") or 0.0) < 0.8: missing_basic.append("industry (conf >= 0.8)")
    if not facts["company_size"].get("value"): missing_basic.append("company_size")
    if (interp["primary_pain"].get("confidence") or 0.0) < 0.7: missing_basic.append("primary_pain (conf >= 0.7)")
    if (interp["trigger"].get("confidence") or 0.0) < 0.6: missing_basic.append("trigger (conf >= 0.6)")
    if (interp["lens"].get("confidence") or 0.0) < 0.6: missing_basic.append("lens (conf >= 0.6)")
    if len(absence.get("inferred_insights", [])) < 1: missing_basic.append("at least 1 inferred_insight")

    unlocked_basic = len(missing_basic) == 0

    missing_deep = list(missing_basic)
    if (interp["strategic_posture"].get("confidence") or 0.0) < 0.6: missing_deep.append("strategic_posture (conf >= 0.6)")
    if (interp["fear"].get("confidence") or 0.0) < 0.5: missing_deep.append("fear (conf >= 0.5)")
    if (interp["ai_maturity"].get("confidence") or 0.0) < 0.5: missing_deep.append("ai_maturity (conf >= 0.5)")
    if len(absence.get("gaps", [])) < 2: missing_deep.append("at least 2 gaps")
    if not facts["org_context"].get("value"): missing_deep.append("org_context")

    unlocked_deep = unlocked_basic and (len(missing_deep) == 0)

    return {
        "basic": {"unlocked": unlocked_basic, "missing": missing_basic},
        "deep": {"unlocked": unlocked_deep, "missing": missing_deep}
    }

# ---------------------------------------------------------
# 6. SPLIT-SCREEN DASHBOARD (Part 3)
# ---------------------------------------------------------
st.sidebar.title("⚙️ Simulation Commands")
if st.sidebar.button("🔄 Fresh Start (Reset Profile)", use_container_width=True):
    reset_session()

st.sidebar.markdown("---")
st.sidebar.subheader("✍️ Manual Override")
with st.sidebar.form("override_form"):
    field_to_override = st.selectbox("Field", ["industry", "company_size", "primary_pain", "fear", "trigger", "lens"])
    override_val = st.text_input("New Manual Value")
    submit_override = st.form_submit_button("Apply Manual Lock")
    
    if submit_override and override_val:
        for grp in ["facts", "interpretation"]:
            if field_to_override in st.session_state.profile[grp]:
                st.session_state.profile[grp][field_to_override] = {
                    "value": override_val,
                    "confidence": 1.0,
                    "source": "manual",
                    "evidence": "Manually overridden by operator",
                    "manual_locked": True,
                    "conflict_flag": False
                }
                st.session_state.last_changes.append(f"🔒 MANUAL LOCK ON {field_to_override} -> {override_val}")
                st.rerun()

# Layout: Left (Chat Pane) | Right (Thinking Pane)
col_chat, col_brain = st.columns([1, 1])

# --- LEFT COLUMN: EXECUTIVE CHAT ---
with col_chat:
    st.subheader("💬 Executive Conversation")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            
    if prompt := st.chat_input("CEO input response..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
            
        with st.spinner("Executing Call A (Chat) & Call B (Extraction)..."):
            ai_response = call_a_chat(prompt)
            call_b_extraction(prompt)
            
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
            st.rerun()

# --- RIGHT COLUMN: BRAIN / THINKING PANE ---
with col_brain:
    st.subheader("🧠 System Thinking Pane (Live Profile)")
    
    # 1. Gatekeeper Status
    gate_status = check_gate_thresholds(st.session_state.profile)
    st.markdown("#### 🚪 Gatekeeper Status")
    
    if gate_status["basic"]["unlocked"]:
        st.success("🟢 Basic Diagnosis: UNLOCKED")
    else:
        st.error(f"🔴 Basic Diagnosis: LOCKED")
        st.caption(f"Missing criteria: {', '.join(gate_status['basic']['missing'])}")

    # Dry Refusal Diagnostic Trigger
    if st.button("🧪 Request Basic Diagnosis"):
        if not gate_status["basic"]["unlocked"]:
            st.code(f"HARD GATEKEEPER REFUSAL (PROGRAMMATIC GATEWAY):\nDiagnosis generation blocked. Insufficient parameters:\n- " + "\n- ".join(gate_status['basic']['missing']), language="text")
        else:
            st.success("Basic Diagnosis generation authorized by Gateway rules!")

    st.markdown("---")
    
    # 2. Current Turn Changes
    if st.session_state.last_changes:
        st.markdown("#### ⚡ Turn Updates")
        for change in st.session_state.last_changes:
            st.info(change)

    # 3. Profile Table Rendering
    st.markdown("#### 📋 Profile Table")
    
    def render_group(group_name: str, group_dict: dict):
        st.markdown(f"**{group_name}**")
        for field, attr in group_dict.items():
            if isinstance(attr, dict) and "value" in attr:
                val = attr.get("value") or "---"
                conf = attr.get("confidence", 0.0)
                src = attr.get("source", "n/a")
                ev = attr.get("evidence") or "No evidence anchor"
                lock = "🔒 LOCKED" if attr.get("manual_locked") else ""
                conflict = "⚠️ CONFLICT" if attr.get("conflict_flag") else ""
                
                color = "#d4edda" if attr.get("value") else "#f8d7da"
                
                st.markdown(f"""
                <div style="background-color: {color}; padding: 8px; border-radius: 5px; margin-bottom: 5px; color: black;">
                    <b>{field}</b>: {val} {lock} {conflict}<br>
                    <small>Conf: {conf} | Source: {src} | Anchor: <i>"{ev}"</i></small>
                </div>
                """, unsafe_allow_html=True)

    render_group("Group A - Facts", st.session_state.profile["facts"])
    render_group("Group B - Interpretation", st.session_state.profile["interpretation"])
    
    st.markdown("**Group C - Absence & Gaps**")
    st.write("💡 **Inferred Insights:**", st.session_state.profile["absence"]["inferred_insights"])
    st.write("🧩 **Noticed Gaps:**", st.session_state.profile["absence"]["gaps"])
