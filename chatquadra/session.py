"""One conversation between a user and a Replier.

On every user message the session:
  1. starts the user analysis in the background (every N messages, see settings.analysis_every),
  2. generates the persona's reply at the same time,
  3. returns the reply with a realistic delivery plan.
The analysis result is collected separately via `inference()`.
"""

from __future__ import annotations

import logging
import random
import threading
import time
import uuid
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor

from .config import Settings, settings as default_settings
from .inference import UserReader, analyze_user, type_candidate, typing_summary, word_count
from .llm import LLM, LLMError
from .personas import get_persona
from .prompts import opener_stage_direction, persona_context_note, persona_system_prompt
from .replier import generate_turn, turn_as_history_text, turn_bubbles
from .schemas import InferenceResult, ReplierTurn, TypingStats
from .timing import plan_delivery
from .typedata import TYPES

log = logging.getLogger(__name__)

# Shared worker pool for background analyses across all sessions.
_ANALYSIS_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="chatquadra-analysis")

# Messages sent within this window of the previous one count as a "burst".
BURST_WINDOW_S = 8.0


class RateLimited(Exception):
    pass


class ChatSession:
    def __init__(
        self,
        persona_code: str,
        user_name: str,
        typing_consent: bool = False,
        settings: Settings | None = None,
        llm: LLM | None = None,
        seed: int | None = None,
        known_type: str | None = None,
    ):
        self.settings = settings or default_settings
        self.llm = llm or LLM(self.settings)
        self.persona = get_persona(persona_code)
        known = (known_type or "").strip().upper()
        if known and known not in TYPES:
            raise ValueError(f"Unknown type: {known_type!r}")
        # When the user tells us their type, we don't analyse their messages at all.
        self.known_type = known or None
        self.user_name = (user_name or "").strip()[:40] or "Friend"
        self.typing_consent = typing_consent
        self.id = uuid.uuid4().hex
        self.rng = random.Random(seed)

        self.system_prompt = persona_system_prompt(self.persona, self.user_name)
        self.api_messages: list[dict] = []  # append-only history sent to the model
        self.transcript: list[dict] = []  # what the UI shows
        self.user_texts: list[str] = []
        self.typing: list[TypingStats] = []
        self._send_times: list[float] = []
        self._recent_sends: deque[float] = deque()
        self._bursts = 0
        self._note_shared = ""

        self.reader = UserReader(self.settings.min_words)
        self._analysis: Future | None = None
        self._lock = threading.RLock()
        self.feedback: list[dict] = []

    # --- public API -----------------------------------------------------------------------------

    def open(self) -> dict:
        """The persona greets the user first."""
        with self._lock:
            self.api_messages.append({"role": "user", "content": opener_stage_direction(self.user_name)})
            turn = self._reply(last_user_text=None)
            return self._finish_turn(turn, user_text="")

    def send(self, text: str, typing: TypingStats | None = None) -> dict:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty message")
        text = text[: self.settings.max_message_chars]
        with self._lock:
            self._check_rate()
            # Where everything stood before this send, so a failed reply can be undone cleanly.
            marks = (len(self._send_times), self._bursts, len(self.user_texts), len(self.typing),
                     len(self.transcript), len(self.api_messages), self._note_shared)
            now = time.time()
            if self._send_times and now - self._send_times[-1] <= BURST_WINDOW_S:
                self._bursts += 1
            self._send_times.append(now)
            self.user_texts.append(text)
            if typing is not None and self.typing_consent:
                self.typing.append(typing)
            self.transcript.append({"speaker": "user", "text": text, "ts": now})
            self.api_messages.append({"role": "user", "content": text})

            # (1) Start the user analysis first; it runs in parallel with the reply.
            analysis_started = self._maybe_start_analysis()

            # Share the latest finished read with the persona, as a private note.
            note = self.reader.persona_note
            if self.settings.persona_reads_user and note and note != self._note_shared and not self.llm.mock:
                self.api_messages.append({"role": "system", "content": persona_context_note(self.user_name, note)})
                self._note_shared = note

            # (2) The persona replies in character.
            try:
                turn = self._reply(last_user_text=text)
            except LLMError:
                self._undo_send(marks)
                raise
            result = self._finish_turn(turn, user_text=text)
            result["analysis_started"] = analysis_started
            return result

    def inference(self) -> InferenceResult:
        if self.known_type:
            return InferenceResult(
                ready=True,
                self_reported=True,
                words_analysed=word_count(self.user_texts),
                messages_analysed=len(self.user_texts),
                top_types=[type_candidate(self.known_type, 1.0, ["You told us your type."])],
                impression=f"You told us you're an {self.known_type}, so ChatQuadra isn't analysing how you write.",
                basis="Your own type, as you told us.",
            )
        with self._lock:
            pending = self._analysis is not None and not self._analysis.done()
            return self.reader.result(
                stats=list(self.typing),
                burst_ratio=self._burst_ratio(),
                pending=pending,
                next_update_in=self._next_update_in(),
            )

    def wait_for_analysis(self, timeout: float = 60.0) -> None:
        future = self._analysis
        if future is not None:
            try:
                future.result(timeout=timeout)
            except Exception:  # already logged in the worker
                pass

    def add_feedback(self, sounds_like_me: bool, actual_type: str | None = None) -> None:
        with self._lock:
            self.feedback.append(
                {
                    "sounds_like_me": sounds_like_me,
                    "actual_type": (actual_type or "").upper() or None,
                    "shown": [t.type for t in self.inference().top_types],
                    "ts": time.time(),
                }
            )

    # --- internals ------------------------------------------------------------------------------

    def _reply(self, last_user_text: str | None) -> ReplierTurn:
        return generate_turn(
            self.llm,
            self.persona,
            self.system_prompt,
            self.api_messages,
            effort=self.settings.reply_effort,
            last_user_text=last_user_text,
            rng=self.rng,
        )

    def _finish_turn(self, turn: ReplierTurn, user_text: str) -> dict:
        self.api_messages.append({"role": "assistant", "content": turn_as_history_text(turn)})
        now = time.time()
        for text in turn_bubbles(turn):
            self.transcript.append({"speaker": "replier", "text": text, "emotion": turn.emotion, "ts": now})
        plan = plan_delivery(turn, self.persona.pace, user_text, self.settings.pace, self.rng)
        return {"turn": turn.model_dump(), "plan": plan}

    def _maybe_start_analysis(self) -> bool:
        if self.known_type:
            return False
        if len(self.user_texts) % self.settings.analysis_every != 0:
            return False
        if self._analysis is not None and not self._analysis.done():
            return False  # one at a time; the next cadence point will catch up
        texts = list(self.user_texts)
        summary = typing_summary(list(self.typing), self._burst_ratio())
        self._analysis = _ANALYSIS_POOL.submit(self._run_analysis, texts, summary)
        return True

    def _run_analysis(self, texts: list[str], summary: str) -> None:
        try:
            analysis, style_notes = analyze_user(self.llm, self.persona, texts, summary, self.settings.analysis_effort)
        except LLMError as exc:
            log.warning("User analysis failed: %s", exc)
            return
        except Exception:
            log.exception("User analysis crashed")
            return
        if analysis is None:
            return
        with self._lock:
            self.reader.apply(analysis, words=word_count(texts), messages=len(texts), style_notes=style_notes)

    def _next_update_in(self) -> int:
        every = self.settings.analysis_every
        remainder = len(self.user_texts) % every
        return every - remainder if remainder else every

    def _burst_ratio(self) -> float:
        return self._bursts / max(1, len(self._send_times) - 1)

    def _undo_send(self, marks: tuple) -> None:
        """Forget a send whose reply failed: the message, its note, its typing stats and its rate slot."""
        sends, bursts, texts, typing, transcript, api, note = marks
        del self._send_times[sends:], self.user_texts[texts:], self.typing[typing:]
        del self.transcript[transcript:], self.api_messages[api:]
        self._bursts, self._note_shared = bursts, note
        if self._recent_sends:
            self._recent_sends.pop()

    def _check_rate(self) -> None:
        now = time.time()
        while self._recent_sends and now - self._recent_sends[0] > 3600:
            self._recent_sends.popleft()
        if len(self._recent_sends) >= self.settings.max_messages_per_hour:
            raise RateLimited("Message limit reached for this hour. Please take a break and come back.")
        self._recent_sends.append(now)
