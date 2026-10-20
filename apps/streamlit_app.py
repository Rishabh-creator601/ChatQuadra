"""ChatQuadra: Streamlit app.

Run from the project root:
    streamlit run apps/streamlit_app.py
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components  # noqa: E402

import streamlit_pages as pages  # noqa: E402
import streamlit_views as views  # noqa: E402
from chatquadra.config import demo_mode_requested, settings  # noqa: E402
from chatquadra.inference import word_count  # noqa: E402
from chatquadra.llm import LLM, PROVIDERS, LLMError, check_api_key  # noqa: E402
from chatquadra.personas import load_personas  # noqa: E402
from chatquadra.schemas import TypingStats  # noqa: E402
from chatquadra.session import ChatSession, RateLimited  # noqa: E402
from chatquadra.timing import absorb_latency  # noqa: E402
from chatquadra.typedata import GROUPS, NICKNAMES, TYPES, types_in  # noqa: E402

HELP_URL = "https://findahelpline.com"
MAX_STEP_SECONDS = 8.0
# delivery-plan step kind -> what the character is shown doing
PLAYBACK_STATUS = {"read": "is reading…", "typing": "is typing…", "pause": "paused…", "message": "is here"}
# Developer demo mode (canned replies, no key) only when explicitly switched on.
DEV_MODE = demo_mode_requested()
# Every visitor brings their own key; the server's own key is never used by this app.
USER_SETTINGS = replace(settings, mock=DEV_MODE)

st.set_page_config(page_title="ChatQuadra", page_icon="🪑", layout="wide")
st.html(views.CSS)
typing_box = components.declare_component("cq_typing", path=str(ROOT / "apps" / "streamlit_typing"))

ss = st.session_state
for key, default in {
    "step": "you", "profile": {}, "nav_open": False,
    "api_key": None, "provider": "openai", "model": None,
    "session": None, "pending": None, "turn_id": 0, "last_nonce": None,
    "last_emotion": "neutral", "last_move": "", "timing": 1.0, "history": [],
}.items():
    ss.setdefault(key, default)


def demo_notice() -> None:
    if DEV_MODE:
        st.info(
            "Developer demo mode: replies are canned sample lines, and the reading comes only from a "
            "writing-style model trained on Reddit."
        )


def unlocked() -> bool:
    return DEV_MODE or bool(ss.api_key)


def key_panel() -> None:
    """Key status in the sidebar, once the navigation is visible. The key itself is entered on page 1."""
    with st.sidebar:
        if DEV_MODE:
            st.caption("Developer demo mode: no API key needed.")
            return
        if ss.api_key:
            st.markdown(f"**{PROVIDERS[ss.provider]} key connected**")
            st.caption(f"Model {ss.model}. Key ending …{ss.api_key[-4:]}, kept only for this browser session.")
            if st.button("Remove key", width="stretch"):
                ss.api_key = None
                ss.nav_open = False
                end_conversation(next_step="you")


# --- Steps 1 and 2: about you, choose someone -----------------------------------------------------

STEPS = ("About you", "Choose someone", "Talk")
KNOW = "I know my MBTI"
DONT_KNOW = "I don't know my MBTI"


def you_step() -> None:
    st.html(views.stepper_html(STEPS, 0))
    left, right = st.columns([11, 9], gap="large")
    with right:
        st.html(views.table_of_faces_html())
    with left:
        you_form()


def you_form() -> None:
    st.markdown("# Pull up a chair.")
    st.markdown(
        "Sixteen people, each with their own way of talking. Tell us what to call you, then choose who to sit with."
    )
    demo_notice()
    with st.container(key="cq-box-you"):
        st.markdown("### First, a little about you")
        name = st.text_input(
            "Your first name", value=ss.profile.get("name", ""), max_chars=40,
            placeholder="What should they call you?",
        )
        if ss.profile.get("known_type"):
            knows_index = 0
        elif ss.profile:
            knows_index = 1
        else:
            knows_index = None  # first visit: nothing chosen yet
        knows = st.radio("Do you know your personality type?", [KNOW, DONT_KNOW], index=knows_index)
        known_type, consent = None, False
        if knows == KNOW:
            options = list(TYPES)
            current = ss.profile.get("known_type")
            known_type = st.selectbox(
                "Your type", options, index=options.index(current) if current in options else None,
                placeholder="Choose your four letters",
                format_func=lambda c: f"{c} ({NICKNAMES[c]})",
            )
            st.caption("We'll use your type as given and won't analyse your messages.")
        elif knows == DONT_KNOW:
            consent = st.toggle(
                "Also let my typing rhythm count toward the reading",
                value=ss.profile.get("consent", False),
                help="We measure timing only (pauses, edits, speed), never what you typed and deleted.",
            )

        key, provider = None, ss.provider
        if not unlocked():
            ids = list(PROVIDERS)  # Anthropic, OpenAI
            provider = st.radio(
                "AI platform", ids, index=ids.index(ss.provider), horizontal=True,
                format_func=lambda pid: PROVIDERS[pid],
            )
            key = st.text_input(
                f"Your {PROVIDERS[provider]} API key", type="password",
                placeholder="sk-ant-…" if provider == "anthropic" else "sk-…",
                help="ChatQuadra runs on your own key. It's checked with one tiny request, kept only in this "
                "browser session's memory, and never saved.",
            )

        if not st.button("Continue", type="primary"):
            return
        if knows is None:
            st.error("Choose whether you know your MBTI.")
            return
        if knows == KNOW and not known_type:
            st.error("Choose your type, or select \"I don't know my MBTI\".")
            return
        if key is not None:
            with st.spinner("Checking your API key…"):
                problem, model = check_api_key(provider, key, USER_SETTINGS.model)
            if problem:
                st.error(problem)
                return
            ss.api_key, ss.provider, ss.model = key.strip(), provider, model
        ss.profile = {"name": name.strip(), "known_type": known_type, "consent": consent}
        ss.step = "choose"
        st.rerun()


def choose_step() -> None:
    locked = not unlocked()
    st.html(views.stepper_html(STEPS, 1))
    name = ss.profile.get("name") or "there"
    st.markdown(f"# Who would you like to sit with, {name}?")
    st.markdown("Each character holds a conversation in their own way. Pick someone and they'll start talking.")
    if st.button("Back to about you"):
        ss.step = "you"
        st.rerun()
    demo_notice()

    personas = load_personas()
    for group, (group_name, _) in GROUPS.items():
        with st.container(key=f"cq-box-{group.lower()}"):
            st.markdown(f'<h3 class="cq-group-title">{group_name}</h3>', unsafe_allow_html=True)
            st.markdown(f'<p class="cq-group-blurb">{views.GROUP_BLURBS[group]}</p>', unsafe_allow_html=True)
            for col, code in zip(st.columns(4, gap="medium"), types_in(group)):
                persona = personas[code]
                with col, st.container(key=f"cq-person-{code.lower()}"):
                    st.html(views.persona_card_html(persona))
                    if st.button(f"Sit with {persona.name}", key=f"sit-{code}", disabled=locked,
                                 width="stretch"):
                        start_conversation(code)


def start_conversation(code: str) -> None:
    if not unlocked():
        ss.step = "you"
        st.rerun()
    session = ChatSession(
        code, ss.profile.get("name", ""), typing_consent=ss.profile.get("consent", False),
        settings=USER_SETTINGS,
        llm=LLM(USER_SETTINGS, api_key=None if DEV_MODE else ss.api_key, provider=ss.provider, model=ss.model),
        known_type=ss.profile.get("known_type"),
    )
    started = time.time()
    try:
        with st.spinner(f"{session.persona.name} is pulling up a chair…"):
            result = session.open()
    except LLMError as exc:
        st.error(f"{session.persona.name} couldn't join: {exc}")
        return
    ss.session = session
    ss.step = "talk"
    ss.nav_open = True  # the navigation appears once someone has been chosen
    ss.turn_id = 0
    ss.last_nonce = None
    ss.last_emotion = "neutral"
    queue_playback(session, result, started)
    st.rerun()


def queue_playback(session: ChatSession, result: dict, started: float) -> None:
    new_bubbles = sum(1 for step in result["plan"] if step["kind"] == "message")
    ss.pending = {
        "plan": result["plan"],
        "from": len(session.transcript) - new_bubbles,
        "started": started,
        "emotion": result["turn"]["emotion"],
    }
    ss.last_move = result["turn"]["move"]


# --- The table ------------------------------------------------------------------------------------

def table() -> None:
    session: ChatSession = ss.session
    persona = session.persona

    with st.sidebar:
        st.markdown(f"### Talking with {persona.name}")
        ss.timing = st.select_slider(
            "Reply timing", options=[0.4, 1.0, 1.4], value=ss.timing,
            format_func=lambda v: {0.4: "Quick", 1.0: "Natural", 1.4: "Unhurried"}[v],
        )
        behind = st.toggle("Behind the scenes", help="Shows which conversational move the character used.")
        if st.button("Leave the table", width="stretch"):
            end_conversation()
        if st.button("Delete this conversation", width="stretch"):
            end_conversation(deleted=True)
        st.caption(f"Need support? [Find a helpline]({HELP_URL}).")
        demo_notice()

    st.html(views.stepper_html(STEPS, 2))
    main, side = st.columns([7, 4], gap="large")
    with main, st.container(key="cq-box-talk"):
        presence = st.empty()
        convo = st.empty()
        input_area = st.container()
    with side:
        reading = st.empty()  # drawn directly while a reply plays out
        live_area = st.container()  # the self-refreshing panel, once the reply has played
        feedback_area = st.container()

    # Handle a newly sent message first (its value is already in session state), then draw
    # the input box so it is locked while the reply plays out.
    input_key = f"cq_input_{session.id}"  # fresh box per conversation, so old values never replay
    value = ss.get(input_key)

    if value and value.get("nonce") != ss.last_nonce and ss.pending is None:
        ss.last_nonce = value["nonce"]
        started = time.time()
        convo.html(views.transcript_html(session.transcript + [{"speaker": "user", "text": value["text"]}], persona, session.user_name))
        presence.html(views.presence_html(persona, ss.last_emotion, f"{persona.name} is reading your message…"))
        typing = TypingStats(**value["typing"]) if value.get("typing") else None
        try:
            result = session.send(value["text"], typing)
        except RateLimited as exc:
            st.warning(str(exc))
            ss.draft = {"id": value["nonce"], "text": value["text"]}
        except LLMError as exc:
            st.error(f"{persona.name} didn't get that: {exc} Your message is back in the box; send it again.")
            ss.draft = {"id": value["nonce"], "text": value["text"]}
        else:
            queue_playback(session, result, started)

    with input_area:
        typing_box(
            consent=session.typing_consent,
            turn_id=ss.turn_id,
            disabled=ss.pending is not None,
            placeholder=f"Say something to {persona.name}…",
            accent=persona.color,
            hint="Enter to send, Shift+Enter for a new line.",
            draft=ss.get("draft"),
            key=input_key,
            default=None,
        )

    if ss.pending is not None:
        draw_reading(session, reading)  # shows "reading your messages now…" while the analysis runs
        play(session, presence, convo)
        st.rerun()

    presence.html(views.presence_html(persona, ss.last_emotion, f"{persona.name} is listening"))
    convo.html(views.transcript_html(session.transcript, persona, session.user_name))
    with live_area:
        live_reading(session)
    with feedback_area:
        draw_feedback(session)
        if behind and ss.last_move:
            st.caption(f"Last move: {ss.last_move}")


def play(session: ChatSession, presence, convo) -> None:
    """Act out the delivery plan: reading, typing, hesitating, sending."""
    persona = session.persona
    pending = ss.pending
    if "next" not in pending:  # first time through: count the wait for the model as reading time
        elapsed_ms = int((time.time() - pending["started"]) * 1000)
        pending["plan"], pending["next"] = absorb_latency(pending["plan"], elapsed_ms), 0
    plan, start = pending["plan"], pending["next"]
    shown = session.transcript[: pending["from"]]
    new_lines = session.transcript[pending["from"]:]
    # Resume where an interrupted run (e.g. a widget change) left off, instead of replaying.
    delivered = sum(1 for step in plan[:start] if step["kind"] == "message")
    emotion = pending["emotion"] if delivered else ss.last_emotion

    for i in range(start, len(plan)):
        step = plan[i]
        kind = step["kind"]
        if kind == "message":
            delivered += 1
            emotion = pending["emotion"]
        if kind in PLAYBACK_STATUS:
            typing = kind == "typing"
            status = f"{persona.name} {PLAYBACK_STATUS[kind]}"
            presence.html(views.presence_html(persona, emotion, status, typing=typing))
            convo.html(views.transcript_html(shown + new_lines[:delivered], persona, session.user_name, typing=typing))
        pending["next"] = i + 1 if kind == "message" else i  # a cut-off pause or typing step is redone
        time.sleep(min(MAX_STEP_SECONDS, step["ms"] * ss.timing / 1000))

    ss.pending = None
    ss.turn_id += 1
    ss.last_emotion = emotion


def draw_reading(session: ChatSession, placeholder) -> None:
    result = session.inference()
    placeholder.html(views.insight_html(result, word_count(session.user_texts), session.settings.min_words))


def live_reading(session: ChatSession) -> None:
    """The reading panel; while an analysis runs it refreshes itself every 2 seconds."""
    was_pending = session.inference().pending
    st.fragment(run_every="2s" if was_pending else None)(_reading_panel)(session, was_pending)


def _reading_panel(session: ChatSession, was_pending: bool) -> None:
    result = session.inference()
    if was_pending and not result.pending:
        st.rerun()  # the analysis just finished: redraw the whole page (feedback buttons, summary)
    st.html(views.insight_html(result, word_count(session.user_texts), session.settings.min_words))


def draw_feedback(session: ChatSession) -> None:
    result = session.inference()
    if not result.ready or result.self_reported:  # nothing to give feedback on when you told us your type
        return
    st.write("")
    col_yes, col_no = st.columns(2)
    if col_yes.button("Sounds like me", width="stretch"):
        session.add_feedback(True)
        st.toast("Noted: this reading sounds like you.")
    if col_no.button("Doesn't sound like me", width="stretch"):
        ss.show_type_picker = True
    if ss.get("show_type_picker"):
        actual = st.selectbox("Do you know your type? (optional)", ["I don't know"] + list(TYPES))
        if st.button("Save feedback", width="stretch"):
            session.add_feedback(False, None if actual == "I don't know" else actual)
            ss.show_type_picker = False
            st.toast("Thanks. We'll use this to improve the reading.")


def end_conversation(deleted: bool = False, next_step: str = "choose") -> None:
    session = ss.get("session")
    if session is not None and not deleted and session.user_texts:
        ss.history.append(pages.snapshot(session))  # kept for the summary page
    for key in ("session", "pending", "last_nonce", "show_type_picker"):
        ss.pop(key, None)
    ss.turn_id = 0
    ss.last_emotion = "neutral"
    ss.step = next_step
    if deleted:
        st.toast("Conversation deleted.")
    st.rerun()


def talk_page() -> None:
    if ss.get("session") is not None:
        table()
    elif ss.step == "choose" and unlocked() and ss.profile:
        choose_step()
    else:
        you_step()


def footer() -> None:
    with st.container(key="cq-footer"):
        with st.expander("Privacy and how this works"):
            st.markdown(
                "- Everyone here is an **AI character** with a personality. They'll tell you if you ask.\n"
                "- The reading is an estimate of how you come across in your typing, not a diagnosis.\n"
                "- Typing rhythm is used only if you switch it on, and only as numbers (timing, edits).\n"
                "- Your API key and conversations live only in this browser session's memory. Leaving or "
                "deleting clears them.\n"
                f"- If you're going through something hard, you can find a helpline at [{HELP_URL}]({HELP_URL})."
            )
        st.caption("ChatQuadra is independent and not affiliated with 16Personalities or The Myers-Briggs Company.")


nav_pages = [
    st.Page(talk_page, title="Talk", icon=":material/forum:", url_path="talk", default=True),
    st.Page(pages.summary_page, title="Your summary", icon=":material/insights:", url_path="summary"),
    st.Page(pages.about_page, title="About", icon=":material/info:", url_path="about"),
    st.Page(pages.references_page, title="References", icon=":material/menu_book:", url_path="references"),
]
ss.talk_page = nav_pages[0]  # lets other pages link back to Talk
navigation = st.navigation(nav_pages, position="sidebar" if ss.nav_open else "hidden")
if ss.nav_open:
    key_panel()
navigation.run()
footer()
