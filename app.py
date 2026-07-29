import streamlit as st
import json
import unicodedata
import difflib
from openai import OpenAI

# 1. OPENAI API INITIALIZATION VIA SECRETS
if "OPENAI_API_KEY" in st.secrets:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
else:
    st.error("⚠️ OPENAI_API_KEY is missing in Streamlit Secrets. Please configure it in your App Settings.")
    client = None

# SYSTEM PROMPT WITH ENGLISH TAXONOMY & STRICT ANCHORING MANDATES
SYSTEM_PROMPT = """
You are an expert Enterprise AI Transformation Architect and Corporate Behavioral Analyst.
Your objective is to parse the latest client transcript turn and populate an anchored, dynamic JSON structure.

[REGIME 1: STRICT FACTUAL DISCIPLINE (SLOTS)]
For the 'slots' object, operate with zero inference. Extract only explicit facts.
- Role / CompanySize / Tech / Pain / RootCauses / Limits: If vague or unmentioned, leave strictly as 'Unknown'. 

[REGIME 2: ANCHORED PSYCHOLOGICAL INFERENCE (HUMAN FACTOR & TAGS)]
Analyze emotional undercurrents, defense mechanisms, and operational priorities.
- 'Not enough signal' is the expected and default state for psychological tags. Never force a classification.
- CRITICAL: Every fear or metadata change MUST be accompanied by a literal, meaningful verbatim quote as evidence. If no substantial evidence exists, do not populate the item.

STRICT DECISION LENS TAXONOMY ENFORCEMENT:
The 'Decision_Lens' object value MUST be selected EXCLUSIVELY from this closed strategic set based on the executive's core corporate mandate:
[
  "Marketing-oriented",
  "Commercial / Revenue-focused",
  "Operational / Technical",
  "Standard"
]

STRICT FEAR TAXONOMY ENFORCEMENT:
For elements in the 'Fears' array, the 'value' field MUST be selected EXCLUSIVELY from the following closed list of standard architectural categories:
[
  "Loss of control",
  "Hidden cost",
  "Team resistance",
  "Image / reputation",
  "Loss of human connection",
  "Technological dependency",
  "Other (see quote)"
]

SAFETY VALVE RULE:
If the user expresses a clear, grounded fear or operational constraint that does not fit into the first 6 specific architectural categories (e.g., legal/regulatory risks, competitive disadvantage, stakeholder pressure), you MUST select "Other (see quote)" as the 'value'. Never force an inaccurate category.

Structure the JSON precisely as follows:
{
  "slots": {"Role": "...", "CompanySize": "...", "Tech": "...", "Pain": "...", "RootCauses": "...", "Limits": "..."},
  "tags": {
    "Fears": [
      {"value": "...", "evidence_quote": "Verbatim quote", "confidence": "Low|Medium|High"}
    ],
    "Hedging_markers": {"detected": true|false, "evidence_quote": "Verbatim quote"},
    "Contradiction_flag": {"detected": true|false, "old_quote": "Past quote", "new_quote": "Current conflicting quote"}
  },
  "calculated_meta": {
    "Decision_Lens": {"value": "Marketing-oriented|Commercial / Revenue-focused|Operational / Technical|Standard", "evidence_quote": "Verbatim quote"},
    "Tech_Profile": {"value": "...", "evidence_quote": "Verbatim quote"},
    "Transformation_Strategy": {"value": "...", "evidence_quote": "Verbatim quote"}
  },
  "ai_guidance": "Tactical coaching instruction..."
}
"""

st.set_page_config(page_title="AI Advisor - Secure Companion", page_icon="🎙️", layout="wide")

# CSS Styling
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: white; }
    .stButton>button { width: 100%; border-radius: 50px; height: 3em; background-color: #2E6BFF; color: white; }
    .status-box-empty { padding: 12px; border-radius: 10px; background-color: #1E2329; border: 1px solid #3E444B; margin-bottom: 8px; color: #6C757D; }
    .status-box-filled { padding: 12px; border-radius: 10px; background-color: #155724; border: 2px solid #28a745; margin-bottom: 8px; color: #D4EDDA; font-weight: bold; }
    .status-box-alert { padding: 12px; border-radius: 10px; background-color: #B7791F; border: 2px solid #F6E05E; margin-bottom: 8px; color: #FEFCBF; font-weight: bold; }
    .recommendation-box { padding: 25px; border-radius: 15px; background-color: #0B2545; border: 2px solid #134074; color: #EEF4F8; margin-top: 15px; margin-bottom: 20px; }
    .priority-badge-high { display: inline-block; background-color: #D69E2E; color: white; padding: 6px 14px; font-size: 0.85em; font-weight: bold; border-radius: 4px; margin-bottom: 15px; }
    .last-input-box { background-color: #1E2530; border-left: 4px solid #2E6BFF; padding: 12px; border-radius: 4px; margin-top: 15px; color: #A0AEC0; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

# Confidence level weight mapping
confidence_map = {"Low": 1, "Medium": 2, "High": 3}

# Standard English stop words list for context deduplication processing
STOPWORDS = {"the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in", "on", "at", "for", "with", "is", "was", "were", "it", "this", "that"}

# TEXT NORMALIZATION UTILITY
def normalize(text):
    """Normalize text to minimize false negatives due to spacing, casing, or accentuation variations."""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', str(text)).lower()
    text = "".join([c for c in text if unicodedata.category(c) != 'Mn'])
    text = text.replace("'", "'").replace("’", "'").replace("«", '"').replace("»", '"').replace("“", '"').replace("”", '"')
    return " ".join(text.split())

# THE DETACHED INTEGRITY ASSURANCE ENGINES
def is_grounded(quote, full_text, threshold=0.85, min_words=3):
    """
    STRICT ANTI-HALLUCINATION GUARD: Verifies that a quote actually exists verbatim 
    or near-verbatim within the text history by checking word sequence order.
    """
    if not quote or not full_text:
        return False
        
    q_words = normalize(quote).split()
    if len(q_words) < min_words:
        return normalize(quote) in normalize(full_text)

    q_norm = normalize(quote)
    f_norm = normalize(full_text)
    
    # Fast path: exact sequential match
    if q_norm in f_norm:
        return True

    # Sliding window sequential matching over chronological text logs
    f_words = f_norm.split()
    window_size = len(q_words) + 2
    
    for i in range(len(f_words) - len(q_words) + 1):
        window = " ".join(f_words[i:i+window_size])
        if difflib.SequenceMatcher(None, q_norm, window).ratio() >= threshold:
            return True
            
    return False

def quotes_refer_to_same_fear(quote_a, quote_b, threshold=0.70):
    """
    FLEXIBLE CONTEXT DEDUPLICATION WITH STOPWORDS FILTER: Compares two short quotes to determine 
    if they point to the same underlying sentiment, ignoring grammatical noise.
    """
    if not quote_a or not quote_b:
        return False
        
    a_set = set(normalize(quote_a).split()) - STOPWORDS
    b_set = set(normalize(quote_b).split()) - STOPWORDS
    
    if not a_set or not b_set:
        return False
        
    union = a_set.union(b_set)
    return len(a_set.intersection(b_set)) / len(union) >= threshold

# HARD RESET
def execute_hard_reset():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state.stage = 1
    st.session_state.slots = {'Role': 'Unknown', 'CompanySize': 'Unknown', 'Tech': 'Unknown', 'Pain': 'Unknown', 'RootCauses': 'Unknown', 'Limits': 'Unknown'}
    st.session_state.tags = {
        'Fears': [],
        'Hedging_markers': {'detected': False, 'evidence_quote': ''},
        'Contradiction_flag': {'detected': False, 'old_quote': '', 'new_quote': ''}
    }
    st.session_state.contradiction_ever_detected = {'detected': False, 'old_quote': '', 'new_quote': ''}
    st.session_state.hedging_ever_detected = {'detected': False, 'evidence_quote': ''}
    st.session_state.calculated_meta = {
        'Decision_Lens': {'value': 'Standard', 'evidence_quote': ''},
        'Tech_Profile': {'value': 'Standard', 'evidence_quote': ''},
        'Transformation_Strategy': {'value': 'Discovery & Architecture Mapping', 'evidence_quote': ''}
    }
    st.session_state.history_by_stage = {'Stage 1': '', 'Stage 2': '', 'Stage 3': '', 'Stage 4': ''}
    st.session_state.last_analyzed = ''
    st.session_state.ai_guidance = "Simulation state completely reset."
    st.session_state.blueprint_generated = False
    st.session_state.step4_validated = False

# INITIALIZE SEED STATE
if 'stage' not in st.session_state: st.session_state.stage = 1
if 'slots' not in st.session_state: st.session_state.slots = {'Role': 'Unknown', 'CompanySize': 'Unknown', 'Tech': 'Unknown', 'Pain': 'Unknown', 'RootCauses': 'Unknown', 'Limits': 'Unknown'}
if 'tags' not in st.session_state: st.session_state.tags = {
    'Fears': [],
    'Hedging_markers': {'detected': False, 'evidence_quote': ''},
    'Contradiction_flag': {'detected': False, 'old_quote': '', 'new_quote': ''}
}
if 'contradiction_ever_detected' not in st.session_state: st.session_state.contradiction_ever_detected = {'detected': False, 'old_quote': '', 'new_quote': ''}
if 'hedging_ever_detected' not in st.session_state: st.session_state.hedging_ever_detected = {'detected': False, 'evidence_quote': ''}
if 'calculated_meta' not in st.session_state: st.session_state.calculated_meta = {
    'Decision_Lens': {'value': 'Standard', 'evidence_quote': ''},
    'Tech_Profile': {'value': 'Standard', 'evidence_quote': ''},
    'Transformation_Strategy': {'value': 'Discovery & Architecture Mapping', 'evidence_quote': ''}
}
if 'history_by_stage' not in st.session_state: st.session_state.history_by_stage = {'Stage 1': '', 'Stage 2': '', 'Stage 3': '', 'Stage 4': ''}
if 'last_analyzed' not in st.session_state: st.session_state.last_analyzed = ''
if 'ai_guidance' not in st.session_state: st.session_state.ai_guidance = "Welcome. Input the initial statement."
if 'blueprint_generated' not in st.session_state: st.session_state.blueprint_generated = False
if 'step4_validated' not in st.session_state: st.session_state.step4_validated = False

# SIDEBAR SIMULATION CONTROL
st.sidebar.markdown("## ⚙️ Simulation Control")
if st.sidebar.button("🔄 Reset Simulation State", use_container_width=True):
    execute_hard_reset()
    st.rerun()

web_context_input = st.sidebar.text_area("Public Corporate Profile Context:", height=150, placeholder="Inject manual environment data here...", key="web_ctx_static")

def verify_and_merge_tags(incoming_tags, incoming_meta, full_raw_text):
    """
    Unified evaluation engine. Validates factual grounding bounds sequentially, 
    manages contradictions, and dynamically accumulates executive fears without category-based collisions.
    """
    # 1. Processing Hedging Markers with strict sequence verification
    if 'Hedging_markers' in incoming_tags and isinstance(incoming_tags['Hedging_markers'], dict):
        inc_detected = incoming_tags['Hedging_markers'].get("detected", False)
        inc_quote = incoming_tags['Hedging_markers'].get("evidence_quote", "")
        
        if inc_detected and inc_quote and is_grounded(inc_quote, full_raw_text):
            st.session_state.tags['Hedging_markers'] = {"detected": True, "evidence_quote": inc_quote}
            st.session_state.hedging_ever_detected = {"detected": True, "evidence_quote": inc_quote}
        else:
            st.session_state.tags['Hedging_markers'] = {"detected": False, "evidence_quote": ""}

    # 2. Processing Contradiction Flags with strict sequence checks
    if 'Contradiction_flag' in incoming_tags and isinstance(incoming_tags['Contradiction_flag'], dict):
        inc_detected = incoming_tags['Contradiction_flag'].get("detected", False)
        old_q = incoming_tags['Contradiction_flag'].get("old_quote", "")
        new_q = incoming_tags['Contradiction_flag'].get("new_quote", "")
        
        if inc_detected and old_q and new_q and is_grounded(old_q, full_raw_text, threshold=0.90, min_words=5) and is_grounded(new_q, full_raw_text, threshold=0.90, min_words=5):
            st.session_state.tags['Contradiction_flag'] = {"detected": True, "old_quote": old_q, "new_quote": new_q}
            st.session_state.contradiction_ever_detected = {"detected": True, "old_quote": old_q, "new_quote": new_q}
        else:
            st.session_state.tags['Contradiction_flag'] = {"detected": False, "old_quote": "", "new_quote": ""}

    # 3. Dynamic Fear Accumulation Matrix Architecture (Anti-Collision Engine)
    legacy_fears = []
    if 'Fear_primary' in incoming_tags and isinstance(incoming_tags['Fear_primary'], dict):
        legacy_fears.append(incoming_tags['Fear_primary'])
    if 'Fear_secondary' in incoming_tags and isinstance(incoming_tags['Fear_secondary'], dict):
        legacy_fears.append(incoming_tags['Fear_secondary'])

    incoming_fears_list = incoming_tags.get('Fears', legacy_fears)

    if isinstance(incoming_fears_list, list):
        for inc_fear in incoming_fears_list:
            val = inc_fear.get("value", "Not enough signal").strip()
            quote = inc_fear.get("evidence_quote", "").strip()
            conf = inc_fear.get("confidence", "Low")
            
            if val == "Not enough signal" or not quote:
                continue
                
            # STRICT ANTI-HALLUCINATION BOUNDARY LAYER (Sequence Check)
            if not is_grounded(quote, full_raw_text):
                continue
                
            duplicate_found = False
            
            # SAFE DEDUPLICATION ROUTINE (Filtered Token Overlapping Check)
            for idx, old_fear in enumerate(st.session_state.tags['Fears']):
                if quotes_refer_to_same_fear(old_fear['evidence_quote'], quote, threshold=0.70):
                    duplicate_found = True
                    
                    old_conf = old_fear.get("confidence", "Low")
                    if confidence_map.get(conf, 1) > confidence_map.get(old_conf, 1):
                        st.session_state.tags['Fears'][idx] = {
                            "value": val, 
                            "evidence_quote": quote, 
                            "confidence": conf
                        }
                    break
            
            if not duplicate_found:
                st.session_state.tags['Fears'].append({
                    "value": val, 
                    "evidence_quote": quote, 
                    "confidence": conf
                })

    # 4. Calculated Metadata (Non-Regression Persistence Layer)
    DEFAULTS = {
        "Decision_Lens": "Standard",
        "Tech_Profile": "Standard",
        "Transformation_Strategy": "Discovery & Architecture Mapping"
    }
    if isinstance(incoming_meta, dict):
        for key in st.session_state.calculated_meta:
            if key in incoming_meta and isinstance(incoming_meta[key], dict):
                inc_val = incoming_meta[key].get("value", DEFAULTS[key])
                inc_quote = incoming_meta[key].get("evidence_quote", "")
                old_val = st.session_state.calculated_meta[key].get("value", DEFAULTS[key])
                
                if inc_val != DEFAULTS[key]:
                    if not inc_quote or not is_grounded(inc_quote, full_raw_text):
                        continue
                    # Accept grounded specific classification
                    st.session_state.calculated_meta[key] = {"value": inc_val, "evidence_quote": inc_quote}
                elif old_val == DEFAULTS[key]:
                    # Overwrites "Standard" only if current value is already default
                    st.session_state.calculated_meta[key] = {"value": inc_val, "evidence_quote": inc_quote}

def analyze_with_openai(user_text, context_web, current_stage):
    if not user_text or client is None:
        return "No text input captured."

    st.session_state.history_by_stage[f"Stage {current_stage}"] += f" | {user_text}"
    full_conversation_history = " ".join(st.session_state.history_by_stage.values())

    prompt_analyse = (
        f"Current Interview Stage: {current_stage}\n"
        f"Manual Web Context: {context_web}\n"
        f"Latest Client Input Turn: {user_text}\n"
        f"Full Chronological History: {json.dumps(st.session_state.history_by_stage)}\n"
        f"Current State Matrix: {json.dumps(st.session_state.slots)}\n"
        f"Current Meta Matrix: {json.dumps(st.session_state.calculated_meta)}\n"
        f"Current Tags Matrix: {json.dumps(st.session_state.tags)}\n"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_analyse}
            ],
            temperature=0.0
        )
        result = json.loads(response.choices[0].message.content)
        
        # FIXED: Non-Destructive Memory Update Engine
        incoming_slots = result.get("slots", {})
        for key in st.session_state.slots:
            if key in incoming_slots:
                val = str(incoming_slots[key]).strip()
                
                is_valid_incoming = val not in ["", "None", "null", "undefined", "Unknown", "Empty"]
                current_is_empty = st.session_state.slots[key] in ["Unknown", "Empty", ""]
                
                if is_valid_incoming or current_is_empty:
                    if val in ["Unknown", "Empty"] and not current_is_empty:
                        continue
                    st.session_state.slots[key] = val
                    
        # Verify, Ground, and Merge Tags & Meta Parameters
        verify_and_merge_tags(result.get("tags", {}), result.get("calculated_meta", {}), full_conversation_history)

        return result.get("ai_guidance", "Turn parsed successfully.")
    except Exception as e:
        return f"Error analyzing input: {e}"

# UI VIEWPORT
st.markdown(f"### 💬 AI Adoption Interview: Step {st.session_state.stage} / 4")
stage_questions = {
    "1": "Who am I speaking with today, what is the scale of your organization, and what corporate trigger brought you here?",
    "2": "What does your current software infrastructure look like? Are your daily workflows mostly manual or cloud-based?",
    "3": "Where are your teams losing the most hours, and if we deployed AI tomorrow, what are your core operational fears or constraints?",
    "4": "Reviewing your strategic situation: Here is what we know. Do you want to add, modify, or complete any data before receiving your final custom blueprint?"
}
st.markdown(f"#### 👉 {stage_questions[str(st.session_state.stage)]}")

col1, col2 = st.columns([2, 1])

with col1:
    st.info(f"💡 Active Coaching Guidance:\n{st.session_state.ai_guidance}")
    manual_input = st.text_area("✍️ Executive Input (Type or paste notes here):", height=120, key=f"input_stage_{st.session_state.stage}")
    
    if st.button("⚡ Analyze and Validate Input"):
        if manual_input:
            st.session_state.last_analyzed = manual_input
            st.session_state['ai_guidance'] = analyze_with_openai(manual_input, web_context_input, st.session_state.stage)
            if st.session_state.stage == 4:
                st.session_state.step4_validated = True
            st.rerun()
            
    if st.session_state.last_analyzed:
        st.markdown(f"<div class='last-input-box'><b>Last Analyzed Input:</b> {st.session_state.last_analyzed}</div>", unsafe_allow_html=True)

    st.markdown("---")
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.session_state.stage > 1:
            if st.button("⏮️ Previous Stage"):
                st.session_state.stage -= 1
                st.session_state.blueprint_generated = False
                st.session_state.step4_validated = False
                st.rerun()
    with nav_col2:
        if st.session_state.stage < 4:
            if st.button("➡️ Next Stage"):
                st.session_state.stage += 1
                st.session_state.blueprint_generated = False
                st.session_state.step4_validated = False
                st.rerun()

with col2:
    st.markdown("### 📊 Extracted Factual Parameters")
    for key, val in st.session_state.slots.items():
        box_class = "status-box-filled" if val not in ["Unknown", "Empty"] else "status-box-empty"
        st.markdown(f"<div class='{box_class}'><b>{key}:</b> {val}</div>", unsafe_allow_html=True)
        
    st.markdown("#### 🧠 Grounded Psychological Subtext")
    
    derived_lens = st.session_state.calculated_meta['Decision_Lens']['value']
    derived_tech_profile = st.session_state.calculated_meta['Tech_Profile']['value']
    derived_strategy = st.session_state.calculated_meta['Transformation_Strategy']['value']

    box_lens = "status-box-filled" if derived_lens != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{box_lens}'><b>Decision Filter (Lens):</b> {derived_lens}</div>", unsafe_allow_html=True)
    
    box_tech = "status-box-filled" if derived_tech_profile != "Standard" else "status-box-empty"
    st.markdown(f"<div class='{box_tech}'><b>Tech Profile:</b> {derived_tech_profile}</div>", unsafe_allow_html=True)
    
    # Render Dynamic Fears Array (Sorted by Confidence Level)
    st.markdown("<b>Accumulated Operational Fears:</b>", unsafe_allow_html=True)
    if st.session_state.tags.get('Fears'):
        sorted_fears = sorted(
            st.session_state.tags['Fears'], 
            key=lambda x: confidence_map.get(x.get('confidence', 'Low'), 1), 
            reverse=True
        )
        for idx, fear in enumerate(sorted_fears):
            st.markdown(f"""<div class='status-box-filled' style='border-left: 4px solid #D69E2E;'>
                🔴 <b>Fear #{idx+1}:</b> {fear['value']} ({fear['confidence']} Conf.)<br>
                <span style='font-size:0.85em; font-weight:normal; font-style:italic;'>Verbatim: "{fear['evidence_quote']}"</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-empty'>No specific operational fears logged yet.</div>", unsafe_allow_html=True)

    # Render Hedging Markers
    hm_current = st.session_state.tags['Hedging_markers']
    hm_historical = st.session_state.hedging_ever_detected
    
    if hm_current['detected']:
        st.markdown(f"""<div class='status-box-filled'>
            ⚠️ <b>Hesitation (Current Turn):</b> True<br>
            <span style='font-size:0.85em; font-weight:normal; font-style:italic;'>Marker: "{hm_current['evidence_quote']}"</span>
        </div>""", unsafe_allow_html=True)
    elif hm_historical['detected']:
        st.markdown(f"""<div class='status-box-filled' style='background-color: #2b3a4a; border-color: #4a5a6a;'>
            ℹ️ <b>Hesitation (Past History):</b> Retained<br>
            <span style='font-size:0.85em; font-weight:normal; font-style:italic;'>Observed: "{hm_historical['evidence_quote']}"</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-empty'><b>Hesitation Markers:</b> None</div>", unsafe_allow_html=True)

    # Render Anchored Contradiction Banner (Damped severity from Alert to Warning color mapping)
    ct = st.session_state.contradiction_ever_detected
    if ct['detected']:
        st.markdown(f"""<div class='status-box-alert'>
            ℹ️ CHRONOLOGICAL DRIFT DETECTED (MODERATE / GUARDED)<br>
            <span style='font-size:0.8em; font-weight:normal; display:block; margin-top:4px;'>• <b>Past Context:</b> "{ct['old_quote']}"</span>
            <span style='font-size:0.8em; font-weight:normal; display:block;'>• <b>Adjustment / Shift:</b> "{ct['new_quote']}"</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("<div class='status-box-empty'><b>Chronological Alignment:</b> Consistent</div>", unsafe_allow_html=True)

# BLUEPRINT COMPILATION GATE
if st.session_state.stage == 4:
    filled_count = sum(1 for val in st.session_state.slots.values() if val not in ["Unknown", "Empty"])
    
    if st.session_state.step4_validated:
        st.markdown("---")
        st.subheader("🛡️ Strategic Gatekeeper Blueprint Compilation Control")
        
        if filled_count >= 3:
            if st.button("🎯 Compile Custom Strategic Blueprint", type="primary", use_container_width=True):
                st.session_state.blueprint_generated = True
                st.rerun()
        else:
            st.warning("🛑 Blueprint locked: The slots matrix requires at least 3 valid parameters in memory.")

    if st.session_state.blueprint_generated and filled_count >= 3 and st.session_state.step4_validated:
        st.header(f"📋 Comprehensive Strategic Blueprint — [Strategy: {derived_strategy}]")
        
        with st.spinner("Compiling anchored architecture blueprint documentation..."):
            # FIXED: Explicit segregation between confirmed stack and psychological anchors to prevent technical conflation
            prompt_final = f"""
            Act as an elite Human-Centric AI Adoption Architect. Generate a report built strictly on these targets:
            - CONFIRMED FACTUAL TECH STACK (the ONLY technologies that may be referenced as real infrastructure): {json.dumps(st.session_state.slots.get('Tech', 'Unknown'))}
            - Persistent Contradiction History: {json.dumps(st.session_state.contradiction_ever_detected)}
            - Calculated Technology Profile: {derived_tech_profile}
            - Strategic Transformation Path: {derived_strategy}
            - Decision Filter Alignment Lens: {derived_lens}

            PSYCHOLOGICAL EVIDENCE ONLY (fears with illustrative verbatim quotes — these describe the executive's ANXIETY, NOT a technical request, infrastructure choice, or capability to build toward):
            {json.dumps(st.session_state.tags['Fears'])}

            CRITICAL ANTI-HALLUCINATION & CONFLATION MANDATE:
            - Any technology, protocol, or architecture term (e.g., blockchain, Kubernetes, vector database, zero-trust) that appears ONLY inside a Fears evidence_quote and NOT in the Confirmed Factual Tech Stack above MUST NEVER be proposed, recommended, or referenced as a real system, feature, or implementation target.
            - If an unconfirmed buzzword or metaphor (e.g., blockchain) appears in the Fears list, treat it solely as an indicator of corporate technical confusion. Acknowledge the underlying anxiety (e.g., trust, tracking, control) but do NOT use the word or build it into the solution strategy.
            - Resolve the underlying fears using ONLY the confirmed tech stack.

            REPORT STRATEGIC MANDATES:
            1. BRIDGE, DO NOT REPLACE: Respect corporate human constraints by explicitly formulating workflows around legacy dependencies from the confirmed stack only.
            2. EXECUTIVE BLUEPRINT SYNTAX: Use precise business architecture headers:
               - Revenue Protection Strategy
               - Core Architectural Principles
               - Ecosystem Integration Priorities
            """
            
            try:
                final_diag = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt_final}],
                    temperature=0.0
                ).choices[0].message.content

                # Damped severity evaluation logic
                risk_level = "MODERATE / GUARDED" if st.session_state.contradiction_ever_detected['detected'] else "ADAPTIVE / OPEN"
                badge_color = "#B7791F" if st.session_state.contradiction_ever_detected['detected'] else "#0B2545"

                fears_summary = "".join([f"<br>• <b>Fear Anchor:</b> {f['value']} (Verbatim: \"{f['evidence_quote']}\")" for f in st.session_state.tags['Fears']]) if st.session_state.tags['Fears'] else "<br>• No specific fear anchors detected."

                st.markdown(f"""
                <div class="recommendation-box" style="border-color: {badge_color};">
                    <div class="priority-badge-high" style="background-color: {badge_color};">⚠️ HUMAN FACTOR RISK STATUS: {risk_level}</div>
                    <div style="font-size: 0.9em; margin-top: -10px; color: #EEF4F8;">
                        <b>Human & Corporate Posture Risk Assessment:</b>{fears_summary}<br><br>
                        • <b>Ecosystem Directive:</b> Build seamless workflow bridges into existing workspaces natively based on a <b>{derived_lens}</b> structural layout.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(final_diag)
            except Exception as e:
                st.error(f"Error compiling strategic document asset: {e}")
