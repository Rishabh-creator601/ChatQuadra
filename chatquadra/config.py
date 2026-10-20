"""Runtime settings, read from environment variables (and an optional .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
ROSTER_PATH = ROOT / "personas" / "roster.json"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines; existing environment variables win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(ROOT / ".env")


def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        value = default
    return max(low, min(high, value))


def _float(name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(os.environ.get(name, default))
    except ValueError:
        value = default
    return max(low, min(high, value))


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model: str
    reply_effort: str
    analysis_effort: str
    analysis_every: int  # run the user analysis every N user messages (3-5)
    min_words: int  # words needed before showing a result
    pace: float  # multiplier on all realistic delays (1.0 = natural)
    persona_reads_user: bool  # pass the analysis to the persona as a private note
    mock: bool  # canned replies + heuristic analysis, no API calls
    max_message_chars: int
    max_messages_per_hour: int


def demo_mode_requested() -> bool:
    """True only when CHATQUADRA_MOCK is explicitly switched on (the Streamlit app's developer demo mode)."""
    return _bool("CHATQUADRA_MOCK", False)


def load_settings() -> Settings:
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    mock_env = os.environ.get("CHATQUADRA_MOCK")
    # Explicit setting wins; otherwise fall back to mock mode when no key is configured.
    mock = _bool("CHATQUADRA_MOCK", False) if mock_env is not None else not has_key
    return Settings(
        model=os.environ.get("CHATQUADRA_MODEL", "claude-opus-5-5"),
        reply_effort=os.environ.get("CHATQUADRA_REPLY_EFFORT", "low"),
        analysis_effort=os.environ.get("CHATQUADRA_ANALYSIS_EFFORT", "medium"),
        analysis_every=_int("CHATQUADRA_ANALYSIS_EVERY", 3, 3, 5),
        min_words=_int("CHATQUADRA_MIN_WORDS", 150, 20, 2000),
        pace=_float("CHATQUADRA_PACE", 1.0, 0.1, 2.0),
        persona_reads_user=_bool("CHATQUADRA_PERSONA_READS_USER", True),
        mock=mock,
        max_message_chars=_int("CHATQUADRA_MAX_MESSAGE_CHARS", 2000, 100, 10000),
        max_messages_per_hour=_int("CHATQUADRA_MAX_MESSAGES_PER_HOUR", 120, 1, 10000),
    )


settings = load_settings()
