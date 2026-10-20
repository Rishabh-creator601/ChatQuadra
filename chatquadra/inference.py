"""Reading the user: text analysis + typing signals -> axes -> top-2 types.

Method: knowledge/05-inference-signals.md
"""

from __future__ import annotations

import math
import statistics

from .llm import LLM
from .mock import mock_analysis
from .personas import Persona
from .prompts import ANALYSIS_SYSTEM, analysis_user_content
from .schemas import AxisView, InferenceResult, TextAnalysis, TypeCandidate, TypingStats
from .style_model import blend, style_reading
from .typedata import AXES, GROUPS, NICKNAMES, STACKS, TYPES, group_of

# How strongly a fresh reading replaces the running estimate. Each reading sees the
# whole transcript, so it carries more information than the previous one.
NEW_READING_WEIGHT = 0.6
# Steepness of the lean -> probability curve. Deliberately flat so we never over-claim.
CURVE = 2.0
# Words at which text evidence counts fully.
FULL_EVIDENCE_WORDS = 400
# Multipliers for types whose dominant / auxiliary function was spotted.
DOMINANT_CUE_BOOST = 1.15
AUXILIARY_CUE_BOOST = 1.07


def word_count(texts: list[str]) -> int:
    return sum(len(t.split()) for t in texts)


def type_candidate(code: str, confidence: float, why: list[str]) -> TypeCandidate:
    group_name, color = GROUPS[group_of(code)]
    return TypeCandidate(
        type=code, nickname=NICKNAMES[code], group_name=group_name, color=color, confidence=confidence, why=why
    )


def analyze_user(
    llm: LLM, persona: Persona, user_messages: list[str], typing_summary: str, effort: str
) -> tuple[TextAnalysis | None, list[str]]:
    """Read the user. Returns (analysis, writing-style notes).

    Claude's reading is the main signal; the Reddit-trained style model is blended in as a
    weaker supporting signal. In demo mode the style model stands in for Claude.
    """
    style = style_reading(user_messages)
    style_notes = style[1] if style else []
    if llm.mock:
        return (style[0] if style else mock_analysis(user_messages)), style_notes
    analysis = llm.structured(
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": analysis_user_content(user_messages, persona, typing_summary)}],
        output_model=TextAnalysis,
        effort=effort,
    )
    if analysis is not None and style:
        analysis = blend(analysis, style[0])
    return analysis, style_notes


# --- Typing behaviour ---------------------------------------------------------------------------

def _median(values: list[int | None]) -> float | None:
    clean = [v for v in values if v is not None]
    return statistics.median(clean) if len(clean) >= 3 else None


def typing_nudges(stats: list[TypingStats], burst_ratio: float) -> tuple[dict[str, float], list[str]]:
    """Small, capped lean adjustments from typing behaviour (negative = first letter)."""
    nudges = {name: 0.0 for name, _, _ in AXES}
    notes: list[str] = []

    latency = _median([s.reply_latency_ms for s in stats])
    if latency is not None:
        if latency < 4000:
            nudges["e_i"] -= 0.05
            notes.append("You tend to jump in quickly after a message (minor signal toward E).")
        elif latency > 15000:
            nudges["e_i"] += 0.05
            notes.append("You usually take your time before replying (minor signal toward I).")

    if len(stats) >= 3 and burst_ratio >= 0.3:
        nudges["e_i"] -= 0.05
        nudges["j_p"] += 0.03
        notes.append("You often send several messages in a row, thinking out loud (minor signal).")

    pause = _median([s.pause_before_send_ms for s in stats])
    if pause is not None:
        if pause > 2500:
            nudges["j_p"] -= 0.03
            notes.append("You often reread before sending (minor signal toward J).")
        elif pause < 500:
            nudges["j_p"] += 0.03
            notes.append("You send as soon as you finish typing (minor signal toward P).")

    keys = sum(s.keystrokes for s in stats)
    if keys >= 200:
        ratio = sum(s.backspaces for s in stats) / keys
        if ratio > 0.12:
            nudges["j_p"] -= 0.03
            notes.append("You edit your wording a lot before sending (minor signal).")

    if len(stats) >= 3 and sum(s.hesitations for s in stats) / len(stats) >= 1:
        nudges["e_i"] += 0.03
        notes.append("You pause mid-message to find the right words (minor signal toward I).")

    return nudges, notes


def typing_summary(stats: list[TypingStats], burst_ratio: float) -> str:
    _, notes = typing_nudges(stats, burst_ratio)
    return " ".join(notes)


# --- The running estimate -----------------------------------------------------------------------

class UserReader:
    """Keeps the running estimate of how the user comes across."""

    def __init__(self, min_words: int):
        self.min_words = min_words
        self.leans: dict[str, float] = {}
        self.confidences: dict[str, float] = {}
        self.evidence: dict[str, list[str]] = {}
        self.cues: list[str] = []
        self.impression = ""
        self.persona_note = ""
        self.style_notes: list[str] = []
        self.analyses_run = 0
        self.words_at_last_run = 0
        self.messages_at_last_run = 0

    def apply(self, analysis: TextAnalysis, words: int, messages: int, style_notes: list[str] | None = None) -> None:
        self.style_notes = list(style_notes or [])
        for name, _, _ in AXES:
            reading = getattr(analysis, name)
            lean = max(-1.0, min(1.0, reading.lean))
            conf = max(0.0, min(1.0, reading.confidence))
            if name in self.leans:
                lean = (1 - NEW_READING_WEIGHT) * self.leans[name] + NEW_READING_WEIGHT * lean
                conf = (1 - NEW_READING_WEIGHT) * self.confidences[name] + NEW_READING_WEIGHT * conf
            self.leans[name] = lean
            self.confidences[name] = conf
            self.evidence[name] = [e for e in reading.evidence if e.strip()][:3]
        self.cues = list(dict.fromkeys(analysis.function_cues))[:3]
        self.impression = analysis.impression.strip()
        self.persona_note = analysis.persona_note.strip()
        self.analyses_run += 1
        self.words_at_last_run = words
        self.messages_at_last_run = messages

    def result(
        self,
        stats: list[TypingStats],
        burst_ratio: float,
        pending: bool,
        next_update_in: int,
    ) -> InferenceResult:
        words = self.words_at_last_run
        ready = self.analyses_run > 0 and words >= self.min_words
        base = InferenceResult(
            ready=ready,
            pending=pending,
            words_analysed=words,
            messages_analysed=self.messages_at_last_run,
            analyses_run=self.analyses_run,
            next_update_in=next_update_in,
        )
        if not ready:
            return base

        nudges, notes = typing_nudges(stats, burst_ratio)
        evidence_scale = min(1.0, words / FULL_EVIDENCE_WORDS)
        axes: list[AxisView] = []
        p_second: dict[str, float] = {}
        for name, first, second in AXES:
            lean = max(-1.0, min(1.0, self.leans[name] + nudges[name]))
            conf = self.confidences[name]
            x = CURVE * lean * (0.35 + 0.65 * conf * evidence_scale)
            p = 1 / (1 + math.exp(-x))
            p_second[name] = p
            axes.append(AxisView(left=first, right=second, lean=round(lean, 3), p_right=round(p, 3), confidence=round(conf, 3)))

        scores: dict[str, float] = {}
        for code in TYPES:
            prob = 1.0
            for i, (name, first, second) in enumerate(AXES):
                prob *= p_second[name] if code[i] == second else 1 - p_second[name]
            for cue in self.cues:
                if STACKS[code][0] == cue:
                    prob *= DOMINANT_CUE_BOOST
                elif STACKS[code][1] == cue:
                    prob *= AUXILIARY_CUE_BOOST
            scores[code] = prob
        total = sum(scores.values())
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:2]

        top = [type_candidate(code, round(score / total, 3), self._why(code)) for code, score in ranked]
        return base.model_copy(
            update={
                "top_types": top, "axes": axes, "impression": self.impression,
                "typing_signals": notes, "style_signals": self.style_notes,
            }
        )

    def _why(self, code: str) -> list[str]:
        """Evidence from the axes where this type's letter matches the lean, strongest first."""
        picks: list[tuple[float, str]] = []
        for i, (name, first, second) in enumerate(AXES):
            lean = self.leans[name]
            agrees = (code[i] == second and lean > 0.05) or (code[i] == first and lean < -0.05)
            if agrees and self.evidence.get(name):
                picks.append((abs(lean) * self.confidences[name], f"{code[i]}: {self.evidence[name][0]}"))
        picks.sort(reverse=True)
        why = [text for _, text in picks[:3]]
        matched = [c for c in self.cues if c in STACKS[code][:2]]
        if matched:
            why.append(f"Signature of {', '.join(matched)} in how you write")
        return why
