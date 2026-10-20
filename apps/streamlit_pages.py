"""The Summary, About and References pages of the Streamlit app."""

from __future__ import annotations

import json
import time
from html import escape

import streamlit as st

import streamlit_views as views
from chatquadra.avatar import avatar_img
from chatquadra.config import demo_mode_requested, settings
from chatquadra.inference import word_count
from chatquadra.personas import STYLE_METRICS_PATH, load_personas
from chatquadra.schemas import InferenceResult
from chatquadra.session import ChatSession
from chatquadra.style_model import MODEL_PATH
from chatquadra.typedata import GROUPS, types_in


def snapshot(session: ChatSession) -> dict:
    """What we keep about a finished conversation for the summary page (this browser session only)."""
    return {
        "code": session.persona.code,
        "user_name": session.user_name,
        "messages": len(session.user_texts),
        "words": word_count(session.user_texts),
        "reading": session.inference().model_dump(),
        "transcript": [{"speaker": m["speaker"], "text": m["text"]} for m in session.transcript],
        "ended": time.time(),
    }


def _transcript_text(snap: dict) -> str:
    persona = load_personas()[snap["code"]]
    lines = [f"Conversation with {persona.name} ({persona.nickname}, {persona.code}) on ChatQuadra", ""]
    for m in snap["transcript"]:
        who = persona.name if m["speaker"] == "replier" else snap["user_name"]
        lines.append(f"{who}: {m['text']}")
    return "\n".join(lines) + "\n"


def _conversation_block(snap: dict, current: bool, key: str) -> None:
    persona = load_personas()[snap["code"]]
    reading = InferenceResult(**snap["reading"])
    left, right = st.columns([5, 6], gap="large")
    with left:
        st.html(
            f'<div class="cq-presence" style="border:0;padding:0">'
            f'{avatar_img(persona.code, "smile", 88, persona.name + "&#39;s face")}'
            f'<div class="who"><h3 class="cq-display" style="margin:0">{escape(persona.name)}</h3>'
            f'<p class="nick">{escape(persona.nickname)}, {persona.code}</p>'
            f'<p class="stance">{"Talking now" if current else "Finished conversation"}. '
            f'You sent {snap["messages"]} message{"s" if snap["messages"] != 1 else ""} '
            f'({snap["words"]} words).</p></div></div>'
        )
        st.download_button(
            "Download this conversation",
            _transcript_text(snap),
            file_name=f"chatquadra-{persona.name.lower()}.txt",
            mime="text/plain",
            key=f"dl-{key}",
        )
    with right:
        st.html(views.insight_html(reading, snap["words"], settings.min_words))


def summary_page() -> None:
    ss = st.session_state
    st.markdown("# Your summary")
    st.markdown(
        "How you came across in each conversation so far. Each reading is an estimate from the way you type, "
        "not a diagnosis, and different characters can bring out different sides of you."
    )
    current = ss.get("session")
    history = ss.get("history", [])
    if current is None and not history:
        st.info("No conversations yet. Sit with someone on the Talk page, and your summary will appear here.")
        st.page_link(ss["talk_page"], label="Go to Talk", icon=":material/forum:")
        return

    if current is not None:
        st.markdown("## Current conversation")
        _conversation_block(snapshot(current), current=True, key="current")
    if history:
        st.markdown("## Earlier conversations")
        for i, snap in enumerate(reversed(history)):
            _conversation_block(snap, current=False, key=f"h{i}")
            st.divider()

    readings = [InferenceResult(**s["reading"]) for s in history] + (
        [current.inference()] if current is not None else []
    )
    ready = [r for r in readings if r.ready and r.top_types and not r.self_reported]
    if len(ready) >= 2:
        st.markdown("## Across your conversations")
        tally: dict[str, float] = {}
        for r in ready:
            for c in r.top_types:
                tally[c.type] = tally.get(c.type, 0.0) + c.confidence
        ranked = sorted(tally.items(), key=lambda kv: kv[1], reverse=True)[:3]
        st.markdown(
            "Types that came up most often in your readings: "
            + ", ".join(f"**{t}**" for t, _ in ranked)
            + ". If the same types keep appearing with different characters, that's a steadier signal than any "
            "single conversation."
        )
    st.caption("Summaries live only in this browser session. Leaving the site or deleting a conversation clears them.")


def about_page() -> None:
    st.markdown("# About ChatQuadra")
    st.markdown(
        """
ChatQuadra lets you sit across from one of sixteen characters, each built on one of the sixteen personality
types from Jungian type theory, and talk with them the way you'd talk with a person.

### The characters
Each character has a name, a life, a mood and their own way of holding a conversation. Ananya, the INFJ,
listens like a therapist friend and asks one deep question. Alexandra, the ENTJ, takes charge and pushes you to
decide. Kai, the ISTP, barely says a word unless it's useful. They reply in short messages, take time to read and
type, and sometimes hesitate. They are **AI characters**, and they'll tell you so if you sincerely ask.
"""
    )
    personas = load_personas()
    for group, (name, _) in GROUPS.items():
        members = [personas[c] for c in types_in(group)]
        st.markdown(
            f"**{name}**: " + ", ".join(f"{p.name} ({p.code}, {p.stance})" for p in members) + "."
        )
    st.markdown(
        f"""
### How the reading works
Every {settings.analysis_every} messages, while the character is replying, ChatQuadra reads everything you've
written so far and estimates how you come across:

1. **Your words** (only if you don't tell us your type). An AI reading of how you write: reflective or outgoing, concrete or abstract, logical or
   values-led, decided or open. It looks at how you say things, not just the topic.
2. **Your writing style.** A small model trained on how thousands of people write in online type communities
   (sentence length, punctuation, hedging, word choice). It's a weak signal and is weighted that way.
3. **Your typing rhythm** (only if you switch it on). Pauses, edits and speed, measured as numbers only.

The result is the two types you most resemble, with a confidence level and the evidence behind them. You'll see it
after about {settings.min_words} words.

### What it isn't
It isn't a psychological test or a diagnosis. Personality shows only partly in writing, people adapt to whoever
they're talking with, and type labels are a lens rather than a verdict. If a reading doesn't sound like you, say
so with the "Doesn't sound like me" button; that's how it gets better.

### Your API key
ChatQuadra runs on your own API key from **Anthropic** or **OpenAI**, entered on the first page. It's checked with
one tiny request, kept only in this browser session's memory, and never saved. Conversations use your key's credits.
The characters and the reading were written and tuned with Anthropic's Claude, so replies through OpenAI may feel
a little different.

### Privacy
Conversations are kept for this browser session only. Typing rhythm is opt-in and never includes what you typed
or deleted. You can download or delete a conversation at any time.

### If you're struggling
The characters aren't a substitute for real support. If you're going through something hard, you can
[find a helpline near you](https://findahelpline.com).

### Not affiliated
ChatQuadra is independent. It is not affiliated with 16Personalities or The Myers-Briggs Company. MBTI and
Myers-Briggs are trademarks of their owners; we use only the generic four-letter codes.
"""
    )
    if demo_mode_requested():
        st.info("This copy is running in developer demo mode: characters use canned lines.")


def _model_eval_table() -> str | None:
    if not MODEL_PATH.exists():
        return None
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    ev, tr = model["eval"], model["training"]
    rows = ["| Axis | Accuracy (balanced) | AUC |", "|---|---|---|"]
    for name, ax in model["axes"].items():
        scores = ev["axes"][name].get("all", {})
        rows.append(f"| {ax['first']} / {ax['second']} | {scores.get('balanced_accuracy', 0):.0%} | {scores.get('auc', 0):.2f} |")
    four = ev["four_letter"]
    return (
        f"Trained on {tr['documents']:,} short samples from {tr['authors']:,} people, and tested only on people it "
        "never saw in training (5-fold, split by person). 50% accuracy or AUC 0.5 means guessing.\n\n"
        + "\n".join(rows)
        + f"\n\nRight type in its top two: {four['top2']:.0%} of the time (guessing: {four['chance_top2']:.0%})."
    )


def references_page() -> None:
    st.markdown("# References")
    st.markdown(
        """
### Personality theory
- Jung, C. G. (1923). *Psychological Types, or the Psychology of Individuation* (H. G. Baynes, Trans.). Kegan Paul.
  Chapter X, "General Description of the Types", is the main source for our theory notes.
  [Classics in the History of Psychology edition](https://psychclassics.yorku.ca/Jung/types.htm).
- Myers, I. B., with Myers, P. B. (1980). *Gifts Differing: Understanding Personality Type*. Consulting
  Psychologists Press.
- von Franz, M.-L., & Hillman, J. (1971). *Lectures on Jung's Typology* (including von Franz's "The Inferior
  Function"). Spring Publications.
- Quenk, N. L. (2002). *Was That Really Me? How Everyday Stress Brings Out Our Hidden Personality*. Davies-Black.
- Beebe, J. (2016). *Energies and Patterns in Psychological Type: The Reservoir of Consciousness*. Routledge.
- Keirsey, D. (1998). *Please Understand Me II*. Prometheus Nemesis.
- Drenth, A. J. (2013). *The 16 Personality Types: Profiles, Theory, & Type Development*. Inquire Books.
  Used as background reading for function stacks, the inferior function and type development.

### Personality and language
- McCrae, R. R., & Costa, P. T. (1989). Reinterpreting the Myers-Briggs Type Indicator from the perspective of
  the five-factor model of personality. *Journal of Personality, 57*(1), 17–40.
- Pennebaker, J. W., & King, L. A. (1999). Linguistic styles: Language use as an individual difference.
  *Journal of Personality and Social Psychology, 77*(6), 1296–1312.
- Yarkoni, T. (2010). Personality in 100,000 words: A large-scale analysis of personality and word use among
  bloggers. *Journal of Research in Personality, 44*(3), 363–373.
- Monroe, B. L., Colaresi, M. P., & Quinn, K. M. (2008). Fightin' words: Lexical feature selection and
  evaluation for identifying the content of political conflict. *Political Analysis, 16*(4), 372–403.
  (The method used to find each community's distinctive words.)

### Community data
"""
    )
    if STYLE_METRICS_PATH.exists():
        data = json.loads(STYLE_METRICS_PATH.read_text(encoding="utf-8"))["types"]
        items = sum(t["n_items"] for t in data.values())
        authors = sum(t["n_authors"] for t in data.values())
        st.markdown(
            f"Public posts and comments from the sixteen type communities and r/mbti on Reddit, read through the "
            f"[Arctic Shift](https://arctic-shift.photon-reddit.com) archive: {items:,} items from about "
            f"{authors:,} people. Usernames are replaced with salted hashes on download, no text is shown in the "
            "app, and the character notes are our own paraphrased summaries. Types are self-reported, so treat all "
            "community findings as tendencies, not facts."
        )
    else:
        st.markdown("Community statistics haven't been generated on this server.")

    table = _model_eval_table()
    if table:
        st.markdown("### How accurate the writing-style model is")
        st.markdown(table)

    st.markdown(
        """
### Built with
- [Claude](https://www.anthropic.com/claude) by Anthropic or [OpenAI](https://platform.openai.com) models, depending on
  the key you enter: the characters' replies and the main reading.
- [Streamlit](https://streamlit.io) for this app; scikit-learn for training the writing-style model.

### Trademarks
MBTI and Myers-Briggs are trademarks of The Myers-Briggs Company. 16Personalities is a trademark of NERIS Analytics.
ChatQuadra is not affiliated with either, and its character names, nicknames and artwork are its own.
"""
    )
