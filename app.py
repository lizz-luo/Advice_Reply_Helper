import re
import html
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Advice Reply Helper", page_icon="✉️", layout="centered")

HKT = ZoneInfo("Asia/Hong_Kong")

# hint shown under each checklist goal in Step 4
HELP_HINTS = {
    "address_problem":        "talk about the reader's problem",
    "two_advice":             "give 2 or more ideas to help",
    "explain_advice":         "say WHY each idea will help",
    "caring_tone":            "sound kind and encouraging",
    "modal_verbs":            "use: should / could / might / would",
    "conditional_sentences":  "use: If you…, you could…",
    "empathy_phrases":        "use: I understand how you feel…",
    "linking_words":          "use: firstly / moreover / in addition",
    "spelling_punctuation":   "check all spelling and full stops",
    "strong_words": "use strong, expressive words instead of basic ones",
    "greeting_signoff":       "start with Dear… end with Best wishes…",
    "acknowledge_problem":    "show you understand their problem first",
    "separate_paragraphs":    "one idea per paragraph",
    "encouraging_closing":    "end with something hopeful",
}

HELP_OPTIONS = {
    "content": [
        {"value": "address_problem",  "label": "🎯 Address the problem   (= talk about the reader's problem)"},
        {"value": "two_advice",       "label": "💡 Two or more tips   (= give at least 2 pieces of advice)"},
        {"value": "explain_advice",   "label": "🔍 Explain your advice   (= say how each tip can help)"},
        {"value": "caring_tone",      "label": "❤️ Caring tone   (= kind, warm, friendly words)"},
    ],
    "language": [
        {"value": "modal_verbs",           "label": "💪 Modal verbs   (e.g. should, could, might)"},
        {"value": "conditional_sentences", "label": "🔄 Conditional sentences   (e.g. If you…, you could…)"},
        {"value": "empathy_phrases",       "label": "🤗 Empathy phrases   (e.g. I understand how you feel)"},
        {"value": "linking_words",         "label": "🔗 Linking words   (e.g. firstly, also, moreover)"},
        {"value": "spelling_punctuation",  "label": "✏️ Spelling & punctuation   (e.g. ! ? , : .)"},
        {"value": "power word",            "label": "⚡ Power words   (e.g. sad → upset, good → wonderful, happy → delighted)"},
    ],
    "organisation": [
        {"value": "greeting_signoff",    "label": "👋 Greeting & sign-off   (e.g. Dear… / Best wishes)"},
        {"value": "acknowledge_problem", "label": "📨 Acknowledge the problem   (= show you understand first)"},
        {"value": "separate_paragraphs", "label": "📄 Separate paragraphs   (= one idea per paragraph)"},
        {"value": "encouraging_closing", "label": "🌟 Encouraging closing   (= end with hope and support)"},
    ],
}

MODE_DESCRIPTIONS = {
    "content":      "💡 Help me with what I wrote — Get help on your ideas, advice, and tone.",
    "language":     "🔤 Help me with my words — Get help on grammar, linking words, spelling, and more.",
    "organisation": "📄 Help me with how I set up my email — Get help on greeting, paragraphs, sign-off, and more.",
}

HELP_DESC_MAP = {
    "address_problem":        "whether the student clearly addressed and responded to the reader's problem or concern",
    "two_advice":             "whether the student gave at least 2 separate, distinct pieces of advice",
    "explain_advice":         "whether the student explained HOW each piece of advice can help the reader",
    "caring_tone":            "whether the student used a caring, warm, and encouraging tone throughout",
    "modal_verbs":            "whether the student used modal verbs appropriately (e.g. should, could, might, would)",
    "conditional_sentences":  "whether the student used conditional sentences (e.g. If you try..., you could...)",
    "empathy_phrases":        "whether the student used phrases to show empathy (e.g. I understand how you feel)",
    "linking_words":          "whether the student used appropriate linking words (e.g. firstly, moreover, in addition)",
    "spelling_punctuation":   "whether spelling and punctuation are correct throughout",
    "strong_words": "whether the student used strong, expressive vocabulary instead of basic words where appropriate",
    "greeting_signoff":       "whether the student included a proper greeting and sign-off",
    "acknowledge_problem":    "whether the student acknowledged the reader's problem in the opening",
    "separate_paragraphs":    "whether each piece of advice is in its own paragraph",
    "encouraging_closing":    "whether the student ended with an encouraging closing",
}

MODE_DESC_MAP = {
    "content":      "CONTENT (what the student wrote about)",
    "language":     "LANGUAGE (words, grammar, and sentences)",
    "organisation": "ORGANISATION (how the email is structured)",
}


def hk_now_str() -> str:
    return datetime.now(HKT).strftime("%Y-%m-%d %H:%M:%S HKT")


def init_state():
    defaults = {
        "student_name":       "",
        "student_class":      "",
        "student_number":     "",
        "writing_input":      "",
        "selected_mode":      "content",
        "help_values":        [],
        "custom_question":    "",
        "feedback_text":      "",
        "interaction_history": [],
        "interaction_count":  0,
        "step1_confirmed":    False,
        "step2_confirmed":    False,
        "show_save_log_dialog": False,
        "save_log_requested": False,
        "run_feedback_now": False,
        "clear_writing_on_next_run": False,
        "reset_after_step2_on_next_run": False,
        "reset_from_step3_on_next_run": False,
        "scroll_to_step": "",
        "session_history_expanded": False,
        "trigger_auto_download": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def word_count(text: str) -> int:
    text = (text or "").strip()
    return len([w for w in re.split(r"\s+", text) if w]) if text else 0


def build_prompt(writing, student_name, mode, help_values, custom_q):
    category_name = MODE_DESC_MAP[mode]

    # Build goal labels and descriptions for selected goals
    goal_labels = []
    goals_desc_lines = []
    for v in help_values:
        if v in HELP_DESC_MAP:
            # Get short label (strip emoji prefix, take text before " — " or full label)
            raw = next((o["label"] for opts in HELP_OPTIONS.values() for o in opts if o["value"] == v), v)
            # Use just the key name as focus area label (clean short form)
            focus = raw.split("—")[0].strip() if "—" in raw else raw.split("(")[0].strip()
            goal_labels.append((v, focus))
            goals_desc_lines.append(f"- {focus}: {HELP_DESC_MAP[v]}")

    goals_block = "\n".join(goals_desc_lines) if goals_desc_lines else ""

    prompt = (
        f"You are a friendly Advice Reply Helper for primary school students aged 10-11. "
        f"Student name: {student_name}. Feedback category: {category_name}.\n"
        "The student has written an ADVICE REPLY EMAIL — a friendly email responding to someone who asked for help with a problem.\n\n"
        "=== STRICT RULES ===\n"
        "1. NEVER write, rewrite, finish, or complete the student's email — not even one sentence.\n"
        "2. ONLY give feedback on the selected checklist goals listed below.\n"
        "3. Use very simple English suitable for P5 students (age 10-11), including weaker learners. No jargon.\n"
        "4. Be honest and direct about weaknesses — do NOT give vague encouragement instead of real feedback.\n"
        "5. Keep the total response under 400 words.\n\n"
    )

    if goals_block:
        prompt += (
            f"=== CHECKLIST GOALS TO REVIEW ===\n{goals_block}\n\n"
        )

    prompt += (
        "=== PART 1: FEEDBACK TABLE ===\n"
        "Output a Markdown table with EXACTLY these four columns:\n"
        "| Focus Area | What You Did Well | Weakness | Tip |\n"
        "|---|---|---|---|\n"
        "Rules for the table:\n"
        "- One row per checklist goal selected above.\n"
        "- Focus Area: the short name of the goal (e.g. 'Caring tone', 'Modal verbs').\n"
        "- What You Did Well: ONE specific, genuine example from the student's writing. Quote their words if possible. Keep it to 1 sentence.\n"
        "- Weakness: ONE honest, specific weakness in that area. Be direct but kind. 1 sentence only. If the student did well, write 'No major weakness — keep it up!'.\n"
        "- Tip: ONE short, clear, actionable tip to fix the weakness. Max 1-2 sentences. Simple words only.\n\n"
        "=== PART 2: HOW TO MAKE IT BETTER ===\n"
        "After the table, write a section with this exact heading: ✏️ How to Make It Better\n"
        "For EACH checklist goal reviewed, provide TWO concrete before-and-after examples.\n"
        "Use this exact format for every example:\n\n"
        "📌 [Focus Area Name]\n\n"
        "Follow this exact format. Each line must be on its own line. Do not merge lines together:\\n\\n"
        "Example 1:\\n"
        "❌ Your sentence: \"I think you should talk to your friend.\"\\n"
        "✅ Better: \"If you feel upset, you could try talking to your friend about how you feel.\"\\n"
        "💡 Why: This uses a conditional sentence which makes the advice sound more gentle and helpful.\\n"
        "\\n"
        "Example 2:\\n"
        "❌ Your sentence: \"I hope you get better.\"\\n"
        "✅ Better: \"I really hope you feel much better soon — please don't worry too much!\"\\n"
        "💡 Why: Adding warm words like 'really' and 'please don't worry' makes the tone more caring.\\n"
        "\\n"
        "Now follow the same format for the student's email below. Each ❌, ✅, and 💡 line must start on a new line.\\n\\n"
        "Important rules for Part 2:\n"
        "- Always give TWO examples per focus area — never just one.\n"
        "- Quote the student's ACTUAL sentences wherever possible.\n"
        "- Keep improved versions close to the student's original so they feel achievable.\n"
        "- If the student's email is too short to find two examples, create examples showing what they COULD add.\n"
        "- Use only simple vocabulary appropriate for age 10-11.\n\n"
    )

    if custom_q:
        prompt += f"=== STUDENT'S OWN QUESTION ===\n\"{custom_q}\"\nPlease address this question briefly after Part 2.\n\n"

    prompt += f"=== STUDENT'S EMAIL ===\n---\n{writing}\n---"
    return prompt


def get_groq_client():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in Streamlit secrets.")
    return Groq(api_key=api_key)

def post_process_feedback(text: str) -> str:
    markers = ["❌", "✅", "💡", "📌", "Example 1:", "Example 2:"]
    for m in markers:
        text = text.replace(m, f"\n\n{m}")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def get_ai_feedback(prompt: str) -> str:
    client = get_groq_client()
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful encouraging writing coach for primary school students aged 10-11. Follow the user prompt exactly and return concise markdown. When writing examples with lines starting with negative, positive, and idea markers, always put each on its own separate line. Never merge them into one paragraph.",
            },
            {"role": "user", "content": prompt},
        ],
    )
     
    raw = completion.choices[0].message.content.strip()
    return post_process_feedback(raw)


def llm_detect_write_for_me(custom_q: str) -> bool:
    if not custom_q.strip():
        return False
    try:
        client = get_groq_client()
        check_prompt = (
            "You are a safeguard for a primary school writing tool. "
            "Decide whether the student is asking the AI to write, complete, rewrite, or finish their work for them, rather than asking for feedback or tips. "
            f'Student question: "{custom_q}"\n'
            "Reply with ONLY one word: YES or NO."
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=5,
            messages=[{"role": "user", "content": check_prompt}],
        )
        answer = resp.choices[0].message.content.strip().upper()
        return answer.startswith("YES")
    except Exception:
        return False


def escape_html(s: str) -> str:
    return html.escape(s or "")


def do_reset_after_step2():
    st.session_state["selected_mode"] = "content"
    st.session_state["help_values"] = []
    st.session_state["custom_question"] = ""
    st.session_state["feedback_text"] = ""
    st.session_state["show_save_log_dialog"] = False
    st.session_state["save_log_requested"] = False
    st.session_state["run_feedback_now"] = False


def do_reset_from_step3():
    st.session_state["help_values"] = []
    st.session_state["custom_question"] = ""
    st.session_state["feedback_text"] = ""
    st.session_state["show_save_log_dialog"] = False
    st.session_state["save_log_requested"] = False
    st.session_state["run_feedback_now"] = False


def do_clear():
    st.session_state["selected_mode"]      = "content"
    st.session_state["help_values"]        = []
    st.session_state["custom_question"]    = ""
    st.session_state["feedback_text"]      = ""
    st.session_state["interaction_history"] = []
    st.session_state["interaction_count"]  = 0
    st.session_state["step1_confirmed"]    = False
    st.session_state["step2_confirmed"]    = False
    st.session_state["show_save_log_dialog"] = False
    st.session_state["save_log_requested"] = False
    st.session_state["run_feedback_now"] = False


def download_log_html() -> bytes:
    history = st.session_state.interaction_history
    name = st.session_state.get("student_name", "").strip() or "Student"
    cls  = st.session_state.get("student_class",  "").strip()
    num  = st.session_state.get("student_number", "").strip()
    rows = [
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"<title>Learning Log - {escape_html(name)}</title>",
        """<style>
body{font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#0c1929;background:#f0f9ff;line-height:1.65}
h1{text-align:center;color:#0369a1;margin-bottom:4px}.subtitle{text-align:center;color:#b45309;font-style:italic;font-weight:700;margin-bottom:24px}
.info,.session{background:#fff;border:1px solid #bae6fd;border-radius:14px;padding:18px;margin-bottom:18px}.tag{display:inline-block;background:#e0f2fe;border-radius:999px;padding:4px 10px;margin:2px 6px 2px 0;font-size:12px}
.sample{background:#f8fbff;border:1px solid #dbeafe;padding:12px 14px;border-radius:8px;white-space:pre-wrap;word-break:break-word;overflow-wrap:anywhere}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:14px}th{background:#0ea5e9;color:#fff;padding:10px;text-align:left}td{padding:10px;border-bottom:1px solid #dbeafe;vertical-align:top}tr:nth-child(even) td{background:#f8fbff}
</style></head><body>""",
        "<h1>✉️ Advice Reply Helper</h1><div class='subtitle'>Learning Log</div>",
        "<div class='info'>",
        f"<p><strong>Student:</strong> {escape_html(name)}</p>",
    ]
    if cls:
        rows.append(f"<p><strong>Class:</strong> {escape_html(cls)}</p>")
    if num:
        rows.append(f"<p><strong>Number:</strong> {escape_html(num)}</p>")
    rows.append(f"<p><strong>Total Sessions:</strong> {len(history)}</p></div>")
    for i, entry in enumerate(history, 1):
        rows += [
            "<div class='session'>",
            f"<h3>Session {i}</h3>",
            f"<div class='tag'>{escape_html(entry['timestamp'])}</div>"
            f"<div class='tag'>{escape_html(entry['mode_label'])}</div>",
        ]
        goals = entry.get("help_goals", [])
        if goals:
            rows.append("<p><strong>Checklist Goals:</strong> " + ", ".join(escape_html(g) for g in goals) + "</p>")
        if entry.get("custom_question"):
            rows.append(f"<p><strong>Custom Question:</strong> {escape_html(entry['custom_question'])}</p>")
        rows += [
            "<p><strong>My Email:</strong></p>",
            f"<div class='sample'>{escape_html(entry['writing'])}</div>",
            "<p><strong>AI Feedback:</strong></p>",
            f"<div>{entry['response']}</div>",
            "</div>",
        ]
    rows.append("</body></html>")
    return "".join(rows).encode("utf-8")


# ── App start ────────────────────────────────────────────────────────────────

init_state()

if st.session_state.pop("_do_reset_after_step2", False) or st.session_state.pop("reset_after_step2_on_next_run", False):
    do_reset_after_step2()
if st.session_state.pop("_do_reset_from_step3", False) or st.session_state.pop("reset_from_step3_on_next_run", False):
    do_reset_from_step3()
if st.session_state.pop("_do_clear", False):
    do_clear()
if st.session_state.pop("clear_writing_on_next_run", False):
    st.session_state["writing_input"] = ""
    st.session_state["step2_confirmed"] = False

scroll_target = st.session_state.pop("scroll_to_step", "")
trigger_auto_download = st.session_state.pop("trigger_auto_download", False)

st.markdown(
    """
<style>
:root {
    --bg: #f0f9ff; --bg-soft: #f8fafc; --panel: #f3f4f6;
    --panel-border: #e2e8f0; --text: #0f172a; --muted: #475569;
    --accent: #0369a1; --accent-soft: #e0f2fe;
    --input-bg: #ffffff; --code-bg: #ffffff;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg: #0f172a; --bg-soft: #111827; --panel: #1f2937;
        --panel-border: #334155; --text: #f8fafc; --muted: #cbd5e1;
        --accent: #7dd3fc; --accent-soft: #082f49;
        --input-bg: #111827; --code-bg: #0b1220;
    }
}
.stApp { background: linear-gradient(160deg, var(--bg) 0%, var(--bg-soft) 100%); color: var(--text); }
.block-container { max-width: 760px; padding-top: 2rem; padding-bottom: 4rem; }
.panel, .hero {
    background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 18px; box-shadow: 0 2px 12px rgba(14,165,233,0.06); color: var(--text);
}
.hero  { padding: 1.8rem 1.5rem; margin-bottom: 1rem; text-align: center; }
.panel { padding: 1.25rem 1.25rem 0.5rem; margin-bottom: 1rem; }
.small-note { color: var(--muted); font-size: 0.92rem; margin: 0; }
.hint-text  { color: var(--muted); font-size: 0.82rem; margin: 0.35rem 0 0 0; font-style: italic; }
.badge { display:inline-block; padding:0.35rem 0.9rem; border-radius:999px; font-size:0.82rem; font-weight:700;
         background:var(--accent-soft); color:var(--accent); border:1px solid var(--panel-border); margin-bottom:0.75rem; }
.help-chip, .history-meta { display:inline-block; padding:0.28rem 0.65rem; border-radius:999px; font-size:0.78rem;
         font-weight:700; background:var(--accent-soft); color:var(--accent); border:1px solid var(--panel-border); margin:0 0.4rem 0.3rem 0; }
input, textarea, .stTextInput input, .stTextArea textarea,
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea,
div[data-baseweb="base-input"] input, div[data-baseweb="select"] > div:first-child {
    background-color: var(--input-bg) !important; color: var(--text) !important;
}
textarea::placeholder, input::placeholder { color: var(--muted) !important; }
label, .stMarkdown, .stCaption, .stRadio, .stMultiSelect, .stSelectbox,
.stTextInput, .stTextArea, .stExpander, .stAlert { color: var(--text) !important; }
hr, [data-testid="stDivider"] { border-color: var(--panel-border) !important; background-color: var(--panel-border) !important; }
.feedback-box, .history-card { background: var(--input-bg); border: 1px solid var(--panel-border); border-radius: 14px; }
.feedback-box { padding: 1rem 1.1rem; margin-top: 0.5rem; }
.history-card { padding: 1rem 1rem 0.5rem; margin-bottom: 0.85rem; }
.next-step-btn > div > button {
    background: linear-gradient(135deg, #0ea5e9, #0284c7) !important;
    color: #ffffff !important; border: none !important; font-weight: 700 !important;
}
@media (prefers-color-scheme: dark) {
    .next-step-btn > div > button {
        background: linear-gradient(135deg, #38bdf8, #0ea5e9) !important;
        color: #ffffff !important;
    }
}
.goal-hint { font-size: 0.78rem; color: var(--muted); margin-top: 0.15rem; padding-left: 0.1rem; }
.footer-note { text-align:center; color: var(--muted); font-size:0.85rem; margin-top:2rem; padding-bottom:1rem; }

.hero-title-row { display:flex; align-items:center; justify-content:center; gap:0.55rem; flex-wrap:wrap; }
.floating-emoji { display:inline-block; font-size:1.9rem; line-height:1; animation: floaty 3.2s ease-in-out infinite; will-change: transform; transform-origin:center; }
.floating-emoji.delay-1 { animation-delay: 0.4s; }
.step-emoji { display:inline-block; margin-right:0.2rem; animation: floaty 3.2s ease-in-out infinite; will-change: transform; transform-origin:center; }
.hero .floating-emoji,
.panel h3 .step-emoji,
.panel h3 .floating-emoji,
.feedback-box .floating-emoji { animation: floaty 3.2s ease-in-out infinite; }
@keyframes floaty {
    0% { transform: translateY(0px) rotate(0deg); }
    50% { transform: translateY(-8px) rotate(-4deg); }
    100% { transform: translateY(0px) rotate(0deg); }
}
@media (prefers-reduced-motion: reduce) {
    .floating-emoji, .step-emoji, .hero .floating-emoji, .panel h3 .step-emoji, .panel h3 .floating-emoji, .feedback-box .floating-emoji { animation: none !important; transform: none !important; }
}

</style>
""",
    unsafe_allow_html=True,
)

if scroll_target or trigger_auto_download:
    scroll_script = f"""
    <script>
    (function() {{
      const targetId = {repr('{SCROLL_PLACEHOLDER}')};
      const doDownload = {'true' if trigger_auto_download else 'false'};
      const parentWin = window.parent || window;
      const parentDoc = parentWin.document || document;

      function scrollToTarget() {{
        if (!targetId) return;

        const iframe = window.frameElement;
        const localTarget = document.getElementById(targetId);
        if (localTarget) {{
          try {{ localTarget.scrollIntoView({{behavior: 'auto', block: 'start'}}); }} catch (e) {{}}
        }}

        try {{
          if (parentWin.location.hash !== '#' + targetId) {{
            parentWin.location.hash = targetId;
          }}
        }} catch (e) {{}}

        try {{
          const anchorInParent = parentDoc.getElementById(targetId);
          if (anchorInParent) {{
            anchorInParent.scrollIntoView({{behavior: 'auto', block: 'start'}});
            return;
          }}
        }} catch (e) {{}}

        try {{
          if (iframe && localTarget) {{
            const frameRect = iframe.getBoundingClientRect();
            const targetRect = localTarget.getBoundingClientRect();
            const absoluteTop = (parentWin.scrollY || parentWin.pageYOffset || 0) + frameRect.top + targetRect.top - 24;
            parentWin.scrollTo(0, Math.max(absoluteTop, 0));
          }}
        }} catch (e) {{}}
      }}

      function triggerDownloadOnce() {{
        if (!doDownload || parentWin.__saveLogAutoClicked) return;
        const buttons = Array.from(parentDoc.querySelectorAll('button'));
        const saveBtn = buttons.find(btn => btn.innerText && btn.innerText.includes('Save Learning Log'));
        if (saveBtn) {{
          parentWin.__saveLogAutoClicked = true;
          saveBtn.click();
        }}
      }}

      [120, 350, 800, 1400].forEach((delay) => {{
        setTimeout(() => {{
          scrollToTarget();
          triggerDownloadOnce();
        }}, delay);
      }});
    }})();
    </script>
    """.replace('{SCROLL_PLACEHOLDER}', scroll_target)
    st.components.v1.html(scroll_script, height=0, width=0)
# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class='hero'>
  <div class='badge'>✉️ Advice Reply Helper</div>
  <div class='hero-title-row'>
    <span class='floating-emoji'>💡</span>
    <h1 style='margin:0 0 0.35rem 0; color: var(--text);'>Advice Reply Helper</h1>
    <span class='floating-emoji delay-1'>✨</span>
  </div>
  <p class='small-note' style='font-style:italic;font-weight:600;'>Your Friendly Helper for Writing a Better Reply!</p>
</div>
""",
    unsafe_allow_html=True,
)

# ── Step 1 ───────────────────────────────────────────────────────────────────
st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.markdown("<h3><span class='floating-emoji step-emoji'>👋</span>Step 1 — About You</h3>", unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
    st.text_input("First Name",   key="student_name",   placeholder="e.g. Sarah")
with c2:
    st.text_input("Class",        key="student_class",  placeholder="e.g. 1A")
with c3:
    st.text_input("Class Number", key="student_number", placeholder="e.g. 12")

st.markdown("<div class='next-step-btn'>", unsafe_allow_html=True)
if st.button("✅ Next Step", use_container_width=True, key="step1_next"):
    if all([
        st.session_state.get("student_name",   "").strip(),
        st.session_state.get("student_class",  "").strip(),
        st.session_state.get("student_number", "").strip(),
    ]):
        st.session_state["step1_confirmed"] = True
        # no st.rerun() — let Streamlit's natural rerun handle it
    else:
        st.warning("Please complete all three fields before continuing.")
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

step1_ok = st.session_state.get("step1_confirmed", False)

# ── Step 2 ───────────────────────────────────────────────────────────────────
st.markdown("<div id='step2-anchor'></div><div class='panel'>", unsafe_allow_html=True)
st.markdown("<h3><span class='floating-emoji step-emoji'>✍️</span>Step 2 — Your Advice Reply Email</h3>", unsafe_allow_html=True)
if not step1_ok:
    st.info("Please complete Step 1 first.")

st.markdown(
    "<p>Paste or type your advice reply email below</p>"
    "<p class='hint-text'>ℹ️ You can paste your whole email or just the part you want help with — "
    "like your greeting, a paragraph, or your ending.</p>",
    unsafe_allow_html=True,
)

st.text_area(
    " ",
    key="writing_input",
    placeholder="Paste your whole email here, or just the part you want feedback on...",
    height=220,
    disabled=not step1_ok,
)

wc = word_count(st.session_state.get("writing_input", ""))
st.caption(f"{wc} word{'s' if wc != 1 else ''}")

st.markdown("<div class='next-step-btn'>", unsafe_allow_html=True)
if st.button("✅ Next Step", use_container_width=True, disabled=not step1_ok, key="step2_next"):
    if len(st.session_state.get("writing_input", "").strip()) > 10:
        st.session_state["step2_confirmed"] = True
        do_reset_after_step2()
        # no st.rerun() — let Streamlit handle it
    else:
        st.warning("Please paste or type at least a few sentences before continuing.")
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

step2_ok = st.session_state.get("step2_confirmed", False)

# ── Step 3 ───────────────────────────────────────────────────────────────────
st.markdown("<div id='step3-anchor'></div><div class='panel'>", unsafe_allow_html=True)
st.markdown("<h3><span class='floating-emoji step-emoji'>🎯</span>Step 3 — What Do You Need Help With?</h3>", unsafe_allow_html=True)
if not step2_ok:
    st.info("Please complete Step 2 first.")

mode = st.radio(
    "Choose a help category",
    options=["content", "language", "organisation"],
    format_func=lambda x: {"content": "Content", "language": "Language", "organisation": "Organisation"}[x],
    key="selected_mode",
    horizontal=True,
    disabled=not step2_ok,
)
if step2_ok and mode:
    st.markdown(f"<p class='small-note'>{MODE_DESCRIPTIONS[mode]}</p>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

step3_ok = step2_ok and bool(mode)

# build goal options for current mode
all_goal_options = []
goal_label_map   = {}
if step3_ok:
    for item in HELP_OPTIONS[mode]:
        all_goal_options.append(item["value"])
        goal_label_map[item["value"]] = item["label"]

current_vals = st.session_state.get("help_values", [])
valid_vals   = [v for v in current_vals if v in all_goal_options]
if valid_vals != current_vals:
    st.session_state["help_values"] = valid_vals

# ── Step 4 ───────────────────────────────────────────────────────────────────
st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.markdown("<h3><span class='floating-emoji step-emoji'>📋</span>Step 4 — Pick Your Goals</h3>", unsafe_allow_html=True)
if not step3_ok:
    st.info("Please complete Step 2 and choose a category first.")
else:
    st.caption("Tick one or more goals you want help with:")

st.multiselect(
    "What would you like feedback on?",
    options=all_goal_options,
    format_func=lambda x: goal_label_map.get(x, x),
    key="help_values",
    disabled=not step3_ok,
)


st.markdown("</div>", unsafe_allow_html=True)

# ── Step 5 ───────────────────────────────────────────────────────────────────
st.markdown("<div class='panel'>", unsafe_allow_html=True)
st.markdown("<h3><span class='floating-emoji step-emoji'>💬</span>Step 5 — Ask Your Own Question <em>(optional)</em></h3>", unsafe_allow_html=True)
st.text_area(
    "Do you have a question about your email?",
    key="custom_question",
    placeholder="e.g. Does my advice sound kind? Did I show I care?",
    height=90,
    disabled=not step3_ok,
)
st.markdown("</div>", unsafe_allow_html=True)

# ── Submit ───────────────────────────────────────────────────────────────────
submit = st.button("📨 Get Help", type="primary", use_container_width=True, disabled=not step3_ok)

if submit:
    writing  = st.session_state.get("writing_input",  "").strip()
    custom_q = st.session_state.get("custom_question", "").strip()
    hvs      = st.session_state.get("help_values",    [])
    md       = st.session_state.get("selected_mode",  "")
    name     = st.session_state.get("student_name",   "").strip()

    if not writing or len(writing) < 10:
        st.error("Please type or paste your advice reply email first (at least a few sentences).")
    elif not hvs and not custom_q:
        st.error("Please select at least one checklist goal, or type your own question.")
    elif llm_detect_write_for_me(custom_q):
        st.warning("I can't write or finish your email for you. Try your best first, then I will give you tips to improve it.")
    else:
        prompt      = build_prompt(writing, name, md, hvs, custom_q)
        goal_labels = [goal_label_map.get(v, v) for v in hvs]
        try:
            with st.spinner("Reviewing your email..."):
                feedback = get_ai_feedback(prompt)
            st.session_state["feedback_text"] = feedback
            st.session_state["interaction_count"] += 1
            st.session_state["interaction_history"].append(
                {
                    "timestamp":    hk_now_str(),
                    "mode":         md,
                    "mode_label":   MODE_DESC_MAP[md],
                    "help_goals":   goal_labels,
                    "custom_question": custom_q,
                    "writing":      writing,
                    "response":     feedback,
                }
            )
            st.session_state["show_save_log_dialog"] = True
            st.rerun()
        except Exception as e:
            st.error(f"Groq API error: {e}")

if st.session_state.get("show_save_log_dialog", False):
    @st.dialog("Save Learning Log?")
    def save_log_dialog():
        st.write("Would you like to save your learning log now?")
        yes_col, later_col = st.columns(2)
        with yes_col:
            if st.button("Yes", use_container_width=True, key="save_log_yes"):
                st.session_state["save_log_requested"] = True
                st.session_state["trigger_auto_download"] = True
                st.session_state["show_save_log_dialog"] = False
                st.rerun()
        with later_col:
            if st.button("Later", use_container_width=True, key="save_log_later"):
                st.session_state["show_save_log_dialog"] = False
                st.rerun()
    save_log_dialog()

# ── Feedback ─────────────────────────────────────────────────────────────────
if st.session_state.get("feedback_text"):
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.markdown("<h3><span class='floating-emoji step-emoji'>✨</span>Your Feedback</h3>", unsafe_allow_html=True)
    count = st.session_state["interaction_count"]
    st.markdown(f"<span class='help-chip'>💬 {count} interaction{'s' if count != 1 else ''}</span>", unsafe_allow_html=True)
    st.markdown("<div class='feedback-box'>", unsafe_allow_html=True)
    st.markdown(st.session_state["feedback_text"])
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ── What's Next ───────────────────────────────────────────────────────────────
if st.session_state.get("interaction_history"):
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    st.subheader("🚀 What Now?")
    nx1, nx2 = st.columns(2)
    with nx1:
        if st.button("🎯 Try Other Goals", use_container_width=True,
                     help="Keep the same email — choose different goals"):
            st.session_state["reset_from_step3_on_next_run"] = True
            st.session_state["session_history_expanded"] = False
            st.session_state["scroll_to_step"] = "step3-anchor"
            st.rerun()
    with nx2:
        if st.button("✏️ Check a New Part of My Email", use_container_width=True,
                     help="Go back to Step 2, clear the email box, and reset later steps"):
            st.session_state["clear_writing_on_next_run"] = True
            st.session_state["reset_after_step2_on_next_run"] = True
            st.session_state["session_history_expanded"] = False
            st.session_state["scroll_to_step"] = "step2-anchor"
            st.rerun()

    if st.session_state.get("save_log_requested", False):
        st.info("Your learning log is ready. Please click Save Learning Log below.")
        st.session_state["save_log_requested"] = False
    st.download_button(
        "💾 Save Learning Log",
        data=download_log_html(),
        file_name=f"Learning_Log_{(st.session_state.get('student_name') or 'Student').replace(' ', '_')}.html",
        mime="text/html",
        use_container_width=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ── Session History ───────────────────────────────────────────────────────────
with st.expander("🧾 Session History", expanded=st.session_state.get("session_history_expanded", False)):
    history = st.session_state.get("interaction_history", [])
    if not history:
        st.write("No feedback sessions yet.")
    else:
        for i, item in enumerate(reversed(history), 1):
            idx = len(history) - i + 1
            st.markdown("<div class='history-card'>", unsafe_allow_html=True)
            st.markdown(f"**Session {idx}**")
            st.markdown(
                f"<span class='history-meta'>🕒 {item['timestamp']}</span>"
                f"<span class='history-meta'>🎯 {item['mode_label']}</span>",
                unsafe_allow_html=True,
            )
            goals = item.get("help_goals", [])
            if goals:
                for g in goals:
                    st.markdown(f"<span class='history-meta'>📋 {g}</span>", unsafe_allow_html=True)
            if item.get("custom_question"):
                st.markdown(f"**Custom question:** {item['custom_question']}")
            st.markdown("**Writing sample**")
            st.text_area(
                label=f"Writing sample {idx}",
                value=item["writing"],
                height=180,
                disabled=True,
                label_visibility="collapsed",
                key=f"history_writing_{idx}",
            )
            st.markdown("**Feedback**")
            st.markdown(item["response"])
            st.markdown("</div>", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='footer-note'>© 2026 Becky Cheung. All Rights Reserved.</div>",
    unsafe_allow_html=True,
)
