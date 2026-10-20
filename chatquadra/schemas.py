"""Data contracts shared by the engine and both apps (see docs/APP_PLAN.md §4)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Emotion = Literal[
    "neutral", "warm", "happy", "excited", "amused", "playful", "curious", "thoughtful",
    "empathetic", "concerned", "serious", "skeptical", "confident", "annoyed", "sad", "embarrassed",
]

FunctionCue = Literal["Ni", "Ne", "Si", "Se", "Ti", "Te", "Fi", "Fe"]


# --- Claude output: the Replier's turn -------------------------------------------------------

class ReplierTurn(BaseModel):
    messages: list[str] = Field(
        description="The texts you send right now, in order. Each one is a separate short message bubble."
    )
    emotion: Emotion = Field(description="The feeling on your face as you send this.")
    intensity: Literal["low", "medium", "high"] = Field(description="How strongly that feeling shows.")
    move: str = Field(description="In a few words, which of your conversational moves you just used.")
    follow_up: str = Field(
        description="An extra text you'd send a little later without being prompted, or an empty string. Use rarely."
    )


# --- Claude output: reading the user ----------------------------------------------------------

class AxisReading(BaseModel):
    lean: float = Field(
        description="-1.0 = clearly the FIRST letter of the pair, +1.0 = clearly the SECOND letter, 0 = no lean."
    )
    confidence: float = Field(description="0.0 (no real evidence) to 1.0 (strong, consistent evidence).")
    evidence: list[str] = Field(
        description="Up to 3 short observations, quoting the user's own words where possible."
    )


class TextAnalysis(BaseModel):
    e_i: AxisReading = Field(description="E (Extraversion, first) vs I (Introversion, second).")
    s_n: AxisReading = Field(description="S (Sensing, first) vs N (Intuition, second).")
    t_f: AxisReading = Field(description="T (Thinking, first) vs F (Feeling, second).")
    j_p: AxisReading = Field(description="J (Judging, first) vs P (Perceiving, second).")
    function_cues: list[FunctionCue] = Field(
        description="Cognitive functions whose signature clearly shows in how the user writes (0-3 items)."
    )
    impression: str = Field(
        description="One or two warm sentences in second person: how the user comes across in their typing."
    )
    persona_note: str = Field(
        description=(
            "A short private note for the user's conversation partner about how the user is engaging right now "
            "(mood, pace, openness, what they seem to need). No type letters, no jargon."
        )
    )


# --- Typing behaviour (measured on the client) --------------------------------------------------

class TypingStats(BaseModel):
    reply_latency_ms: Optional[int] = None  # replier's last message shown -> first keystroke
    compose_ms: Optional[int] = None  # first keystroke -> send
    pause_before_send_ms: Optional[int] = None  # last keystroke -> send
    keystrokes: int = 0
    backspaces: int = 0
    hesitations: int = 0  # typing stopped > 2s and then resumed


# --- What the UI shows -------------------------------------------------------------------------

class TypeCandidate(BaseModel):
    type: str
    nickname: str
    group_name: str
    color: str
    confidence: float  # 0-1
    why: list[str]


class AxisView(BaseModel):
    left: str
    right: str
    lean: float  # -1 (left) .. +1 (right), after typing nudges
    p_right: float  # probability of the right-hand letter
    confidence: float


class InferenceResult(BaseModel):
    ready: bool
    pending: bool = False  # an analysis is running right now
    words_analysed: int = 0
    messages_analysed: int = 0
    analyses_run: int = 0
    next_update_in: int = 0  # user messages until the next analysis
    top_types: list[TypeCandidate] = []
    axes: list[AxisView] = []
    impression: str = ""
    typing_signals: list[str] = []
    style_signals: list[str] = []  # from the Reddit-trained writing-style model
    self_reported: bool = False  # the user told us their type, so no analysis ran
    basis: str = "How you come across in your typing — not a diagnosis."
