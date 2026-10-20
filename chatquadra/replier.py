"""Generate the persona's next in-character turn."""

from __future__ import annotations

import random
import re

from .llm import LLM
from .mock import mock_turn
from .personas import Persona
from .schemas import ReplierTurn

_DECLINED = ReplierTurn(
    messages=["hm. I'd rather not go there.", "what else is on your mind?"],
    emotion="thoughtful",
    intensity="low",
    move="sidestepped a topic",
    follow_up="",
)

_MARKDOWN_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)]|#+)\s+")


def sanitize_turn(turn: ReplierTurn, max_bubbles: int) -> ReplierTurn:
    """Enforce texting shape: no markdown list markers, no empty bubbles, bubble cap."""
    bubbles = [_MARKDOWN_PREFIX.sub("", m).strip() for m in turn.messages]
    bubbles = [b for b in bubbles if b]
    if not bubbles:
        bubbles = ["…"]
    if len(bubbles) > max_bubbles:
        bubbles = bubbles[: max_bubbles - 1] + [" ".join(bubbles[max_bubbles - 1 :])]
    return turn.model_copy(update={"messages": bubbles, "follow_up": turn.follow_up.strip()})


def generate_turn(
    llm: LLM,
    persona: Persona,
    system_prompt: str,
    api_messages: list[dict],
    effort: str,
    last_user_text: str | None,
    rng: random.Random,
) -> ReplierTurn:
    if llm.mock:
        said = "\n".join(m["content"] for m in api_messages if m["role"] == "assistant")
        turn = mock_turn(persona, last_user_text, rng, already_said=said)
    else:
        turn = llm.structured(
            system=system_prompt,
            messages=api_messages,
            output_model=ReplierTurn,
            effort=effort,
        ) or _DECLINED
    return sanitize_turn(turn, persona.pace.max_bubbles)


def turn_bubbles(turn: ReplierTurn) -> list[str]:
    """Every bubble the turn delivers, the optional follow-up last."""
    return [*turn.messages, turn.follow_up] if turn.follow_up else list(turn.messages)


def turn_as_history_text(turn: ReplierTurn) -> str:
    """How the persona's own turn is stored in the conversation history sent to the model."""
    return "\n\n".join(turn_bubbles(turn))
