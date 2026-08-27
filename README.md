# 🎙️ Smart Companion - CEO AI Assistant & Strategic Profiler

Smart Companion is a Streamlit MVP implementing a dual-engine architecture (Call A / Call B) for real-time semantic, psychological, and strategic executive profiling.

---

## 🚀 Key Features

* **Dual-Engine Processing:**
  * **Call A (Conversational Agent):** Manages fluid, empathetic executive dialog using gpt-4o.
  * **Call B (Structured Extractor):** Extracts structured profile data using strict Pydantic schemas in parallel.
* **Real-Time Profile Extraction:** Tracks facts (firmographics, stack), interpretations (pain points, triggers, cognitive lenses), and strategic gaps.
* **Programmatic Gatekeeper:** Enforces quality thresholds before unlocking strategic diagnosis generation.
* **Conflict & Lock Management:** Detects contradictory input (⚠️ CONFLICT) and supports manual overrides (🔒 LOCK).

---

## 🛠️ Quick Start

1. **Clone & Install:**
   git clone https://github.com/sarahfunto/smart-companion.git
   cd smart-companion
   pip install streamlit openai pydantic

2. **Configure Secrets:**
   Add your API key in `.streamlit/secrets.toml`:
   OPENAI_API_KEY = "your-openai-api-key"

3. **Run:**
   streamlit run app.py

---

## 📑 Test Scenarios & Evaluation

1. **Scenario 1 (Cooperative CEO):** Full information provided. Unlocks basic diagnosis generation (🟢 UNLOCKED).
2. **Scenario 2 (Dry CEO):** Insufficient context provided. Programmatically blocked by Gatekeeper (🔴 LOCKED).
3. **Scenario 3 (Contradictory CEO):** Conflicting pain points detected. Triggers visual conflict flag (⚠️ CONFLICT).
