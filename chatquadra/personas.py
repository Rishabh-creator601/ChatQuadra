"""Load the 16 Repliers from personas/roster.json and knowledge/types/*.md."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from .config import KNOWLEDGE_DIR, ROOT, ROSTER_PATH
from .typedata import GROUPS, NICKNAMES, STACKS, TYPES, group_of


@dataclass(frozen=True)
class Pace:
    read_base_ms: int
    wpm: int
    max_bubbles: int
    hesitation: float
    follow_up_chance: float


@dataclass(frozen=True)
class Persona:
    code: str
    name: str
    pronouns: str
    age: int
    life: str
    stance: str
    stance_summary: str
    moves: tuple[str, ...]
    control: str
    avoid: tuple[str, ...]
    pace: Pace
    nickname: str
    group: str
    group_name: str
    color: str
    stack: tuple[str, str, str, str]
    type_profile: str  # full knowledge/types/<CODE>.md text
    sample_lines: tuple[str, ...]
    community_voice: str = ""  # our paraphrase of how this type's community writes (community/reddit/types)
    style_hint: str = ""  # data-driven texting style relative to other types (community/reddit/stats)

    def public_dict(self) -> dict:
        """Fields that are safe and useful to send to a browser."""
        return {
            "code": self.code,
            "name": self.name,
            "pronouns": self.pronouns,
            "age": self.age,
            "life": self.life,
            "stance": self.stance,
            "stance_summary": self.stance_summary,
            "nickname": self.nickname,
            "group": self.group,
            "group_name": self.group_name,
            "color": self.color,
            "stack": list(self.stack),
        }


def _sample_lines(profile: str) -> tuple[str, ...]:
    """Pull the '## Sample lines' bullets out of a type profile."""
    match = re.search(r"## Sample lines[^\n]*\n(.*?)(?:\n## |\Z)", profile, re.S)
    if not match:
        return ()
    lines = []
    for raw in match.group(1).splitlines():
        raw = raw.strip()
        if raw.startswith("- "):
            lines.append(raw[2:].strip().strip('"').strip("“”"))
    return tuple(lines)


COMMUNITY_DIR = ROOT / "community" / "reddit"
STYLE_METRICS_PATH = COMMUNITY_DIR / "stats" / "style_metrics.json"

# Style metrics we turn into texting guidance: (metric, "more" phrase, "less" phrase).
_STYLE_KNOBS = (
    ("median_words", "write longer messages", "keep messages short"),
    ("has_exclaim", "use exclamation marks more", "rarely use exclamation marks"),
    ("emoji_per_100w", "use emoji more", "rarely use emoji"),
    ("starts_lowercase", "often type in lowercase", "usually start with a capital letter"),
    ("has_ellipsis", "trail off with '…' more", "rarely trail off with '…'"),
    ("laughs_per_100w", "say 'lol'/'haha' more", "rarely say 'lol'/'haha'"),
    ("hedges_per_100w", "hedge more ('maybe', 'I think')", "hedge less and state things plainly"),
    ("certainty_per_100w", "use certainty words more ('definitely', 'always')", "avoid absolute words"),
    ("has_question", "ask questions more", "ask fewer questions"),
    ("feeling_per_100w", "talk about feelings more", "talk about feelings less"),
    ("logic_per_100w", "reason out loud more", "reason out loud less"),
    ("profanity_per_100w", "swear a bit more", "rarely swear"),
)
_STYLE_Z_THRESHOLD = 0.8
_STYLE_MIN_ITEMS = 150
_FLAIR_MIN_ITEMS = 300


def _style_hint(code: str) -> str:
    """Relative texting style for this type, from the community statistics (if collected)."""
    if not STYLE_METRICS_PATH.exists():
        return ""
    data = json.loads(STYLE_METRICS_PATH.read_text(encoding="utf-8"))
    # Prefer people who flair themselves as this type: in the smaller subreddits most posts are
    # visitors asking *about* the type, which inflates question and "you" rates.
    flair = data.get("types_flair_only", {}).get(code)
    if flair and flair.get("n_items", 0) >= _FLAIR_MIN_ITEMS and data.get("zscores_flair_only", {}).get(code):
        z, agg = data["zscores_flair_only"][code], flair
    else:
        z, agg = data.get("zscores", {}).get(code), data.get("types", {}).get(code)
    if not z or not agg or agg.get("n_items", 0) < _STYLE_MIN_ITEMS:
        return ""
    picks = []
    for metric, more, less in _STYLE_KNOBS:
        value = z.get(metric, 0.0)
        if value >= _STYLE_Z_THRESHOLD:
            picks.append((value, more))
        elif value <= -_STYLE_Z_THRESHOLD:
            picks.append((-value, less))
    picks.sort(reverse=True)
    return "; ".join(text for _, text in picks[:6])


def _community_voice(code: str) -> str:
    """The '## Voice notes for the persona' section of the community profile, if written."""
    path = COMMUNITY_DIR / "types" / f"{code}.md"
    if not path.exists():
        return ""
    match = re.search(r"## Voice notes for the persona\s*\n(.*?)(?:\n## |\Z)", path.read_text(encoding="utf-8"), re.S)
    return match.group(1).strip() if match else ""


@lru_cache(maxsize=1)
def load_personas() -> dict[str, Persona]:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    personas: dict[str, Persona] = {}
    for code in TYPES:
        spec = roster[code]
        profile = (KNOWLEDGE_DIR / "types" / f"{code}.md").read_text(encoding="utf-8")
        group = group_of(code)
        group_name, color = GROUPS[group]
        personas[code] = Persona(
            code=code,
            name=spec["name"],
            pronouns=spec["pronouns"],
            age=spec["age"],
            life=spec["life"],
            stance=spec["stance"],
            stance_summary=spec["stance_summary"],
            moves=tuple(spec["moves"]),
            control=spec["control"],
            avoid=tuple(spec["avoid"]),
            pace=Pace(**spec["pace"]),
            nickname=NICKNAMES[code],
            group=group,
            group_name=group_name,
            color=color,
            stack=STACKS[code],
            type_profile=profile,
            sample_lines=_sample_lines(profile),
            community_voice=_community_voice(code),
            style_hint=_style_hint(code),
        )
    return personas


def get_persona(code: str) -> Persona:
    personas = load_personas()
    key = code.strip().upper()
    if key not in personas:
        raise KeyError(f"Unknown persona type: {code!r}")
    return personas[key]
