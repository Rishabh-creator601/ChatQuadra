"""Turn a Replier turn into a realistic delivery plan (read -> type -> send -> ...).

The plan is plain data; the Streamlit app plays it back.
Step kinds:
  read     the persona is reading your message ("Seen")
  typing   the typing indicator is on
  pause    the typing indicator stopped (hesitation) or the persona is idle
  message  a bubble is delivered (text holds the message)
"""

from __future__ import annotations

import random

from .personas import Pace
from .schemas import ReplierTurn


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def plan_delivery(
    turn: ReplierTurn,
    pace: Pace,
    user_text: str = "",
    speed: float = 1.0,
    rng: random.Random | None = None,
) -> list[dict]:
    rng = rng or random.Random()
    steps: list[dict] = []

    def add(kind: str, ms: float, text: str = "") -> None:
        steps.append({"kind": kind, "ms": int(ms * speed), "text": text})

    # Reading: longer messages take longer to read; slow readers take longer.
    read_ms = _clamp(pace.read_base_ms + len(user_text) * 18, 400, 7000) * rng.uniform(0.85, 1.2)
    add("read", read_ms)

    chars_per_ms = pace.wpm * 5 / 60_000
    bubbles = [m for m in turn.messages if m.strip()]
    for i, text in enumerate(bubbles):
        typing_ms = _clamp(len(text) / chars_per_ms, 500, 9000) * rng.uniform(0.85, 1.15)
        if rng.random() < pace.hesitation:
            # Start typing, stop, think, start again.
            add("typing", typing_ms * 0.35)
            add("pause", rng.uniform(900, 2400))
            add("typing", typing_ms * 0.65)
        else:
            add("typing", typing_ms)
        add("message", 0, text)
        if i < len(bubbles) - 1:
            add("pause", rng.uniform(200, 800))

    if turn.follow_up.strip():
        add("pause", rng.uniform(3500, 8000))
        add("typing", _clamp(len(turn.follow_up) / chars_per_ms, 500, 6000))
        add("message", 0, turn.follow_up.strip())

    return steps


def absorb_latency(plan: list[dict], elapsed_ms: int) -> list[dict]:
    """Shorten the opening 'read' step by time already spent waiting for the model."""
    adjusted = [dict(step) for step in plan]
    if adjusted and adjusted[0]["kind"] == "read":
        adjusted[0]["ms"] = max(0, adjusted[0]["ms"] - max(0, elapsed_ms))
    return adjusted


def total_ms(plan: list[dict]) -> int:
    return sum(step["ms"] for step in plan)
