"""HTML building blocks for the Streamlit app (rendered with st.html)."""

from __future__ import annotations

from html import escape

from chatquadra.avatar import GROUP_TINTS, avatar_img, expression_for
from chatquadra.personas import Persona, load_personas
from chatquadra.schemas import InferenceResult
from chatquadra.typedata import GROUPS, group_of, types_in

_BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Atkinson+Hyperlegible:wght@400;700&display=swap');
:root { --ink:#23253A; --muted:#6B6F86; --paper:#F6F7FB; --line:#DDE0EC; --white:#FFFFFF; }
html, body, [data-testid="stAppViewContainer"] { background: var(--paper); }
[data-testid="stAppViewContainer"] :is(p, li, label, input, textarea, button, a, div[data-testid="stMarkdownContainer"], .cq-convo, .cq-read, .cq-card) {
  font-family: "Atkinson Hyperlegible", system-ui, sans-serif; }
[data-testid="stAppViewContainer"] h1, [data-testid="stAppViewContainer"] h2, [data-testid="stAppViewContainer"] h3,
.cq-display { font-family: "Bricolage Grotesque", system-ui, sans-serif !important; color: var(--ink); letter-spacing: -0.01em; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebarNav"]::before {
  content: "ChatQuadra"; display: block; padding: 0 0 16px 8px;
  font-family: "Bricolage Grotesque", system-ui, sans-serif; font-weight: 700; font-size: 1.4rem; color: var(--ink);
}
.block-container { padding-top: 2rem; max-width: 1180px; }


.cq-presence { display:flex; gap:22px; align-items:center; padding: 6px 0 18px; border-bottom: 2px solid var(--line); }
.cq-presence .who h2 { margin:0; font-size: 2.1rem; line-height:1.05; }
.cq-presence .nick { margin: 4px 0 0; font-size: 1.05rem; color: var(--ink); }
.cq-presence .stance { margin: 6px 0 0; color: var(--muted); font-size: .95rem; max-width: 46ch; }
.cq-status { display:inline-flex; align-items:center; gap:8px; margin-top: 10px; font-size: .92rem; color: var(--muted); }
.cq-status .dot { width:9px; height:9px; border-radius:50%; background: #3CB371; }
.cq-tag { display:inline-block; margin-left:10px; padding: 2px 10px; border-radius: 999px; font-size: .78rem; background: var(--white); border:1px solid var(--line); color: var(--muted); }

/* column-reverse keeps the scroll pinned to the newest line without any script */
.cq-scroll { display:flex; flex-direction:column-reverse; max-height: 56vh; overflow-y:auto; padding-right: 6px; }
.cq-convo { display:flex; flex-direction:column; gap:6px; padding: 18px 0 8px; }
.cq-speaker { font-size:.82rem; color: var(--muted); margin: 12px 4px 2px; }
.cq-speaker.you { text-align:right; }
.cq-line { max-width: 72%; padding: 10px 15px; border-radius: 18px; font-size: 1.02rem; line-height:1.45; color: var(--ink); white-space: pre-wrap; }
.cq-line.them { align-self:flex-start; background: var(--tint); border-top-left-radius: 6px; }
.cq-line.you { align-self:flex-end; background: var(--white); border: 1.5px solid var(--line); border-top-right-radius: 6px; }
.cq-typing-line { align-self:flex-start; display:inline-flex; gap:5px; padding: 14px 16px; border-radius: 18px; border-top-left-radius:6px; background: var(--tint); }
.cq-typing-line i { width:7px; height:7px; border-radius:50%; background: var(--ink); opacity:.35; animation: cq-bounce 1.2s infinite; }
.cq-typing-line i:nth-child(2) { animation-delay:.15s; } .cq-typing-line i:nth-child(3) { animation-delay:.3s; }
@keyframes cq-bounce { 0%,60%,100% { transform: translateY(0); opacity:.35; } 30% { transform: translateY(-4px); opacity:.8; } }
@media (prefers-reduced-motion: reduce) { .cq-typing-line i { animation:none; } }

.cq-read { border-radius: 22px; background: var(--white); padding: 20px 20px 16px; border: 1.5px solid var(--line); }
.cq-read h3 { margin: 0 0 4px; font-size: 1.35rem; }
.cq-read .basis { color: var(--muted); font-size: .85rem; margin: 0 0 14px; }
.cq-cand { display:flex; gap:12px; align-items:center; padding: 12px; border-radius: 16px; margin-bottom: 10px; background: var(--ctint); }
.cq-cand .pct { font-family:"Bricolage Grotesque", sans-serif; font-weight:700; font-size: 1.7rem; color: var(--ink); min-width: 3.2ch; }
.cq-cand .code { font-weight:700; font-size: 1.05rem; }
.cq-cand .nick { color: var(--ink); font-size:.92rem; }
.cq-cand ul { margin: 6px 0 0 18px; padding:0; color: var(--ink); font-size: .85rem; }
.cq-axis { display:grid; grid-template-columns: 1.4rem 1fr 1.4rem; gap: 8px; align-items:center; margin: 8px 0; font-weight:700; font-size:.9rem; }
.cq-axis .track { position:relative; height: 8px; border-radius: 999px; background: var(--line); }
.cq-axis .mark { position:absolute; top:-4px; width:16px; height:16px; border-radius:50%; background: var(--ink); transform: translateX(-50%); }
.cq-axis span:last-child { text-align:right; }
.cq-impression { margin: 14px 0 6px; font-size: .98rem; line-height:1.45; }
.cq-small { color: var(--muted); font-size: .84rem; line-height: 1.4; }
.cq-read ul.cq-small { margin: 4px 0 10px 18px; padding: 0; }
.cq-progress { height: 8px; border-radius: 999px; background: var(--line); overflow:hidden; margin: 10px 0 6px; }
.cq-progress b { display:block; height:100%; background: var(--ink); border-radius: 999px; }

.cq-card { text-align:center; padding: 14px 8px 4px; border-radius: 22px; background: var(--white); border:1.5px solid var(--line); }
.cq-card .name { font-family:"Bricolage Grotesque", sans-serif; font-weight:700; font-size:1.25rem; margin: 8px 0 0; color: var(--ink); }
.cq-card .meta { color: var(--ink); font-size:.9rem; margin: 2px 0 0; }
.cq-card .stance { color: var(--muted); font-size:.82rem; margin: 6px 0 4px; min-height: 2.4em; }
.cq-group-title { margin: 2px 0 4px; font-size: 1.6rem; }
.cq-group-blurb { color: var(--ink); opacity: .78; margin: 0 0 14px; }

@media (max-width: 640px) {
  .cq-presence { gap: 14px; align-items: flex-start; }
  .cq-presence img { width: 84px; height: 84px; }
  .cq-presence .who h2 { font-size: 1.7rem; }
  .cq-presence .stance { display: none; }
}

/* ---- Page 1: the sixteen faces waiting at the table ---- */
.cq-room { background: var(--ink); border-radius: 30px; padding: 26px 22px 20px; margin-top: 8px; }
.cq-row { display: grid; grid-template-columns: 6.2rem 1fr; align-items: center; gap: 8px; padding: 8px 0; }
.cq-row + .cq-row { border-top: 1px solid rgba(255,255,255,.08); }
.cq-row-label { display: flex; align-items: center; gap: 8px; color: #E6E8F2; font-size: .88rem; font-weight: 700; }
.cq-row-label::before { content: ""; width: 10px; height: 10px; border-radius: 50%; background: var(--gc); flex: none; }
.cq-row-faces { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; }
.cq-seat { margin: 0; text-align: center; }
.cq-seat img { width: 100%; max-width: 72px; height: auto; display: block; margin: 0 auto; }
.cq-seat figcaption { color: #C9CCE0; font-size: .78rem; margin-top: 4px; }
.cq-room-note { color: #C9CCE0; font-size: .86rem; margin: 12px 4px 0; }

/* ---- Step indicator (it is a real sequence, so it's numbered) ---- */
.cq-steps { display:flex; gap: 10px; align-items:center; margin: 0 0 18px; flex-wrap: wrap; }
.cq-step { display:flex; align-items:center; gap:8px; padding: 6px 14px 6px 6px; border-radius: 999px;
  background: var(--white); border: 1.5px solid var(--line); color: var(--muted); font-size: .9rem; }
.cq-step b { display:inline-grid; place-items:center; width: 26px; height: 26px; border-radius: 50%;
  background: var(--line); color: var(--ink); font-size: .85rem; }
.cq-step.done { color: var(--ink); }
.cq-step.done b { background: var(--ink); color: var(--white); }
.cq-step.now { color: var(--ink); border-color: var(--ink); font-weight: 700; box-shadow: 0 4px 14px rgba(35,37,58,.12); }
.cq-step.now b { background: #6E6AE8; color: var(--white); }
.cq-step-line { width: 22px; height: 2px; background: var(--line); }

/* ---- Boxes: each section has its own look ---- */
.st-key-cq-box-you {
  max-width: 620px; background: var(--white); border-radius: 26px; padding: 26px 30px 28px;
  border-top: 6px solid #6E6AE8; box-shadow: 0 22px 48px rgba(35,37,58,.12);
}
/* Question labels on the first card: a little bold */
.st-key-cq-box-you [data-testid="stTextInput"] [data-testid="stWidgetLabel"] p,
.st-key-cq-box-you [data-testid="stRadio"] > [data-testid="stWidgetLabel"] p,
.st-key-cq-box-you [data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p {
  font-weight: 600; font-size: 1rem; color: var(--ink);
}
/* One character = one card: face, name and the "Sit with" link together */
[class*="st-key-cq-person-"] {
  background: var(--white); border-radius: 22px; padding: 0 8px 10px; gap: 0;
  box-shadow: 0 6px 18px rgba(35,37,58,.08); border: 2px solid transparent;
}
[class*="st-key-cq-person-"]:hover, [class*="st-key-cq-person-"]:focus-within { border-color: var(--gc); }
[class*="st-key-cq-person-"] .cq-card { background: transparent; border: 0; padding-bottom: 0; }
[class*="st-key-cq-person-"] button {
  border: 0; background: transparent; box-shadow: none; min-height: 0; padding: 4px 0 6px;
}
[class*="st-key-cq-person-"] button p {
  font-weight: 700; text-decoration: underline; text-decoration-color: var(--gc);
  text-decoration-thickness: 2px; text-underline-offset: 6px;
}
[class*="st-key-cq-person-"] button:disabled p { text-decoration-color: var(--line); }
.st-key-cq-box-talk {
  background: var(--white); border-radius: 26px; padding: 22px 24px 18px; box-shadow: 0 18px 44px rgba(35,37,58,.10);
}
.st-key-cq-box-talk .cq-line.you { background: var(--paper); }
.cq-read { box-shadow: 0 14px 34px rgba(35,37,58,.10); border-color: transparent; }
.st-key-cq-footer {
  margin-top: 48px; padding: 12px 20px 8px; border-radius: 18px; background: #ECEEF5; border: 1.5px dashed var(--line);
}
"""


def _group_box_css() -> str:
    """One box per group on the choose page, in the group's tint and accent (--gc)."""
    boxes = ", ".join(f".st-key-cq-box-{group.lower()}" for group in GROUPS)
    rules = [f"{boxes} {{\n  border-radius: 26px; padding: 22px 24px 24px; margin-bottom: 26px;\n}}"]
    for group, (_, color) in GROUPS.items():
        rules.append(
            f".st-key-cq-box-{group.lower()} {{ background: {GROUP_TINTS[group]}; "
            f"border-left: 7px solid {color}; --gc: {color}; }}"
        )
    return "\n".join(rules)


CSS = f"\n<style>{_BASE_CSS}{_group_box_css()}\n</style>\n"

GROUP_BLURBS = {
    "NT": "Curious about how things work. Expect sharp questions and strong opinions.",
    "NF": "Driven by meaning and people. Expect depth, warmth and honesty about feelings.",
    "SJ": "Steady and dependable. Expect practical care and straight talk.",
    "SP": "Here for the moment. Expect energy, action and a sense of humour.",
}


def table_of_faces_html() -> str:
    """Page 1's right side: all sixteen characters, by group, blinking on their own rhythm."""
    personas = load_personas()
    rows = []
    for i, (group, (group_name, color)) in enumerate(GROUPS.items()):
        seats = []
        for j, code in enumerate(types_in(group)):
            p = personas[code]
            delay = ((i * 4 + j) * 1.37) % 5.5
            face = avatar_img(code, "smile" if (i + j) % 2 else "neutral", 72, f"{p.name}'s face", blink_delay=delay)
            seats.append(f'<figure class="cq-seat">{face}<figcaption>{escape(p.name)}</figcaption></figure>')
        rows.append(f'<div class="cq-row" style="--gc:{color}"><span class="cq-row-label">{group_name}</span>'
                    f'<div class="cq-row-faces">{"".join(seats)}</div></div>')
    return (f'<section class="cq-room" aria-label="The sixteen characters">{"".join(rows)}'
            '<p class="cq-room-note">You choose who to sit with on the next step.</p></section>')


def stepper_html(steps: tuple[str, ...], current: int) -> str:
    parts = []
    for i, label in enumerate(steps):
        state, aria = "", ""
        if i < current:
            state = "done"
        elif i == current:
            state, aria = "now", ' aria-current="step"'
        if i:
            parts.append('<span class="cq-step-line" aria-hidden="true"></span>')
        parts.append(f'<span class="cq-step {state}"{aria}><b>{i + 1}</b>{escape(label)}</span>')
    return f'<nav class="cq-steps" aria-label="Progress">{"".join(parts)}</nav>'


def presence_html(persona: Persona, emotion: str | None, status: str, typing: bool = False) -> str:
    face = avatar_img(persona.code, expression_for(emotion), 132, f"{persona.name}'s face", typing=typing)
    return f"""
<div class="cq-presence">
  <div>{face}</div>
  <div class="who">
    <h2 class="cq-display">{escape(persona.name)}<span class="cq-tag">AI character</span></h2>
    <p class="nick">{escape(persona.nickname)}, {persona.code}, {persona.age}</p>
    <p class="stance">{escape(persona.stance_summary)}</p>
    <div class="cq-status" aria-live="polite"><span class="dot"></span>{escape(status)}</div>
  </div>
</div>"""


def transcript_html(entries: list[dict], persona: Persona, user_name: str, typing: bool = False) -> str:
    tint = GROUP_TINTS[persona.group]
    rows = []
    last = None
    for entry in entries:
        who = entry["speaker"]
        if who != last:
            label = escape(persona.name) if who == "replier" else f"{escape(user_name)} (you)"
            rows.append(f'<div class="cq-speaker {"you" if who == "user" else ""}">{label}</div>')
            last = who
        cls = "them" if who == "replier" else "you"
        rows.append(f'<div class="cq-line {cls}">{escape(entry["text"])}</div>')
    if typing:
        if last != "replier":
            rows.append(f'<div class="cq-speaker">{escape(persona.name)}</div>')
        rows.append('<div class="cq-typing-line" aria-label="typing"><i></i><i></i><i></i></div>')
    return (
        f'<div class="cq-scroll" tabindex="0" aria-label="Conversation">'
        f'<div class="cq-convo" style="--tint:{tint}">{"".join(rows)}</div></div>'
    )


def insight_html(result: InferenceResult, words_so_far: int, min_words: int) -> str:
    if result.self_reported and result.top_types:
        c = result.top_types[0]
        return f"""<div class="cq-read"><h3 class="cq-display">Your type</h3>
<p class="basis">As you told us. Your messages aren't being analysed.</p>
<div class="cq-cand" style="--ctint:{_tint(c.type)}"><div class="pct" style="min-width:auto">{c.type}</div>
<div><div class="code">{escape(c.nickname)}</div><div class="nick">{escape(c.group_name)}</div></div></div>
<p class="cq-small">Want to see how you come across instead? Start a new conversation and choose
"I don't know my MBTI".</p></div>"""
    header = '<h3 class="cq-display">How you come across</h3><p class="basis">Based on how you type, not a diagnosis.</p>'
    if not result.ready:
        pct = min(100, int(100 * words_so_far / max(1, min_words)))
        next_read = f"Next read after {result.next_update_in} more message{'s' if result.next_update_in != 1 else ''}."
        if result.pending:
            detail = "Reading your messages now…"
        elif words_so_far >= min_words:
            detail = f"That's enough to go on. {next_read}"
        else:
            detail = f"{words_so_far} of about {min_words} words. {next_read}"
        return f"""<div class="cq-read">{header}
<p class="cq-impression">Still getting to know how you come across. Keep talking naturally.</p>
<div class="cq-progress" role="progressbar" aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100"><b style="width:{pct}%"></b></div>
<p class="cq-small">{detail}</p></div>"""

    cands = []
    for c in result.top_types:
        why = "".join(f"<li>{escape(w)}</li>" for w in c.why[:3])
        cands.append(
            f'<div class="cq-cand" style="--ctint:{_tint(c.type)}"><div class="pct">{round(c.confidence * 100)}%</div>'
            f'<div><div class="code">{c.type}</div><div class="nick">{escape(c.nickname)}, {escape(c.group_name)}</div>'
            f'{"<ul>" + why + "</ul>" if why else ""}</div></div>'
        )
    axes = "".join(
        f'<div class="cq-axis" aria-label="{a.left} versus {a.right}"><span>{a.left}</span>'
        f'<div class="track"><div class="mark" style="left:{50 + a.lean * 50:.1f}%"></div></div><span>{a.right}</span></div>'
        for a in result.axes
    )
    signals = "".join(f"<li>{escape(s)}</li>" for s in result.typing_signals)
    style = "".join(f"<li>{escape(s)}</li>" for s in result.style_signals)
    n = result.next_update_in
    status = "Updating now…" if result.pending else f"Next update after {n} more message{'s' if n != 1 else ''}."
    return f"""<div class="cq-read">{header}{''.join(cands)}{axes}
<p class="cq-impression">{escape(result.impression)}</p>
{f'<p class="cq-small">Writing-style signals (minor):</p><ul class="cq-small">{style}</ul>' if style else ''}
{f'<p class="cq-small">Typing signals (minor):</p><ul class="cq-small">{signals}</ul>' if signals else ''}
<p class="cq-small">{result.words_analysed} words read. {status}</p></div>"""


def persona_card_html(persona: Persona) -> str:
    return f"""<div class="cq-card">{avatar_img(persona.code, "smile", 104, f"{persona.name}'s face")}
<p class="name">{escape(persona.name)}</p>
<p class="meta">{escape(persona.nickname)}, {persona.code}</p>
<p class="stance">{escape(persona.stance)}</p></div>"""


def _tint(code: str) -> str:
    return GROUP_TINTS[group_of(code)]
