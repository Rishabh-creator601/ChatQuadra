"""Demo mode: canned in-character replies and a simple word-based analysis.

Lets both apps run end to end with no API key and no cost. Real behaviour
comes from Claude; this only exists for development and offline demos.
"""

from __future__ import annotations

import random
import re

from .personas import Persona
from .schemas import AxisReading, ReplierTurn, TextAnalysis

_GROUP_EMOTIONS = {
    "NT": ["thoughtful", "skeptical", "confident", "amused"],
    "NF": ["warm", "empathetic", "curious", "thoughtful"],
    "SJ": ["warm", "concerned", "serious", "neutral"],
    "SP": ["playful", "amused", "excited", "confident"],
}


def mock_turn(persona: Persona, user_text: str | None, rng: random.Random, already_said: str = "") -> ReplierTurn:
    lines = [line for line in persona.sample_lines if line not in already_said] or list(persona.sample_lines) or ["hm."]
    if user_text is None:
        messages = [f"hi — I'm {persona.name}.", rng.choice(lines)]
    else:
        count = max(1, min(persona.pace.max_bubbles, rng.choice([1, 1, 2])))
        messages = rng.sample(lines, k=min(count, len(lines)))
    follow_up = rng.choice(lines) if rng.random() < persona.pace.follow_up_chance * 0.5 else ""
    return ReplierTurn(
        messages=messages,
        emotion=rng.choice(_GROUP_EMOTIONS[persona.group]),  # type: ignore[arg-type]
        intensity=rng.choice(["low", "medium", "high"]),  # type: ignore[arg-type]
        move=f"(demo) {rng.choice(persona.moves)}",
        follow_up=follow_up,
    )


# Word lists: first list leans to the FIRST letter of the pair, second to the SECOND.
_CUES = {
    "e_i": (
        [r"!", r"\bwe\b", r"\bfriends?\b", r"\bparty\b", r"\bhang out\b", r"\bcall\b", r"\blol\b", r"\bomg\b"],
        [r"\bi think\b", r"\bhmm+\b", r"\.\.\.", r"\bquiet\b", r"\balone\b", r"\bmyself\b", r"\bnot sure\b"],
    ),
    "s_n": (
        [r"\d", r"\byesterday\b", r"\btoday\b", r"\bexactly\b", r"\bpractical\b", r"\bhow do i\b", r"\bthen\b"],
        [r"\bwhat if\b", r"\bimagine\b", r"\bmeaning\b", r"\bwhy\b", r"\bpossib", r"\bfuture\b", r"\blike a\b"],
    ),
    "t_f": (
        [r"\bbecause\b", r"\blogic", r"\bactually\b", r"\btechnically\b", r"\bmakes sense\b", r"\befficien", r"\bfact"],
        [r"\bfeel", r"\blove\b", r"\bcare\b", r"\bhurt", r"\bsorry\b", r"\bthank", r"\bkind\b", r"\bmatters?\b"],
    ),
    "j_p": (
        [r"\bplan", r"\bdeadline\b", r"\bdecided\b", r"\bschedule\b", r"\bshould\b", r"\bwill\b", r"\bfinish"],
        [r"\bmaybe\b", r"\bwhatever\b", r"\bidk\b", r"\bmight\b", r"\bsee how\b", r"\banyway\b", r"\bwe'll see\b"],
    ),
}


def _axis(texts: list[str], first: list[str], second: list[str]) -> AxisReading:
    joined = "\n".join(texts).lower()
    a = sum(len(re.findall(p, joined)) for p in first)
    b = sum(len(re.findall(p, joined)) for p in second)
    lean = (b - a) / (a + b + 3)
    side = second if lean > 0 else first
    hits = [p.replace(r"\b", "") for p in side if re.search(p, joined)]
    return AxisReading(
        lean=round(lean, 3),
        confidence=round(min(0.55, (a + b) / 20), 3),
        evidence=[f"(demo) word cue: {h}" for h in hits[:2]],
    )


def mock_analysis(user_messages: list[str]) -> TextAnalysis:
    axes = {name: _axis(user_messages, *lists) for name, lists in _CUES.items()}
    return TextAnalysis(
        **axes,
        function_cues=[],
        impression="(Demo mode) This is a simple word-count estimate. Connect an API key for a real reading.",
        persona_note="(demo) no real read available",
    )
