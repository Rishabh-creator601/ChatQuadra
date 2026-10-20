"""Writing-style features, shared by model training (community/reddit) and the live app.

These describe HOW someone writes (length, punctuation, hedging, pronouns, word-category
rates), not WHAT about. Type jargon is stripped first so "as an INFJ…" can't leak the label.
Keep this module dependency-free: the app scores with plain Python.
"""

from __future__ import annotations

import math
import re

TYPE_TALK_RE = re.compile(
    r"\b([IE][NS][TF][JP]s?|[IE]N[TF]Ps?|[TFSN][ie]|[TFSN][ie]-[TFSN][ie]|mbti|enneagram|"
    r"\dw\d|cognitive functions?|dom|aux|tert|inferior|grip|introverts?|extroverts?|extraverts?|"
    r"intuitives?|sensors?|thinkers?|feelers?|judgers?|perceivers?)\b",
    re.I,
)
URL_RE = re.compile(r"https?://\S+|www\.\S+")
MDLINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
WORD_RE = re.compile(r"[A-Za-z']+")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


def _lexicon(*phrases: str) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases) + r")\b", re.I)


LEX = {
    "hedges": _lexicon("maybe", "perhaps", "probably", "i think", "i guess", "kind of", "kinda", "sort of",
                       "idk", "i don't know", "i dont know", "might", "possibly", "seems", "i feel like", "not sure"),
    "certainty": _lexicon("definitely", "obviously", "clearly", "always", "never", "absolutely", "certainly",
                          "of course", "no doubt", "100%", "for sure"),
    "i_words": _lexicon("i", "me", "my", "mine", "myself", "i'm", "im", "i've", "i'd", "i'll"),
    "we_words": _lexicon("we", "us", "our", "ours", "ourselves", "we're", "let's"),
    "you_words": _lexicon("you", "your", "yours", "yourself", "you're", "youre", "u", "ur"),
    "feeling": _lexicon("feel", "feels", "feeling", "feelings", "felt", "love", "hurt", "sad", "happy", "heart",
                        "care", "emotional", "emotions", "emotion", "anxious", "anxiety", "lonely", "cry",
                        "crying", "scared", "afraid", "hug"),
    "logic": _lexicon("logic", "logical", "logically", "reason", "reasoning", "therefore", "technically",
                      "evidence", "efficient", "objectively", "objective", "makes sense", "rational", "analyze",
                      "analysis", "data", "system"),
    "social": _lexicon("friend", "friends", "people", "family", "party", "hang out", "together", "mom", "dad",
                       "partner", "boyfriend", "girlfriend", "bf", "gf", "husband", "wife", "coworkers", "group"),
    "planning": _lexicon("plan", "plans", "planning", "goal", "goals", "deadline", "schedule", "organize",
                         "organized", "routine", "list", "future", "career"),
    "sensory": _lexicon("look", "looks", "taste", "food", "eat", "music", "sound", "color", "clothes", "outfit",
                        "gym", "body", "smell", "touch", "beautiful"),
    "abstract": _lexicon("meaning", "concept", "theory", "idea", "ideas", "possibility", "possibilities",
                         "pattern", "patterns", "philosophy", "universe", "existential", "imagine", "what if",
                         "abstract"),
    "laughs": _lexicon("lol", "lmao", "lmfao", "haha", "hahaha", "hehe", "rofl", "xd"),
    "profanity": _lexicon("fuck", "fucking", "fucked", "shit", "damn", "hell", "ass", "bitch", "crap", "wtf"),
}

# Plain-language descriptions, used to explain a reading to the user.
FEATURE_LABELS = {
    "log_words": "message length",
    "words_per_sentence": "sentence length",
    "has_exclaim": "exclamation marks",
    "has_question": "asking questions",
    "emoji_per_100w": "emoji",
    "starts_lowercase": "starting in lowercase",
    "has_ellipsis": "trailing off with '…'",
    "has_parens": "side remarks in brackets",
    "caps_words_per_100w": "CAPS for emphasis",
    "digits_per_100w": "numbers and specifics",
    "hedges_per_100w": "hedging ('maybe', 'I think')",
    "certainty_per_100w": "certainty words ('definitely', 'always')",
    "i_words_per_100w": "talking about yourself ('I', 'me')",
    "we_words_per_100w": "'we' and 'us'",
    "you_words_per_100w": "addressing the other person ('you')",
    "feeling_per_100w": "feeling words",
    "logic_per_100w": "logic and reasoning words",
    "social_per_100w": "talking about people",
    "planning_per_100w": "plans and goals",
    "sensory_per_100w": "physical and sensory detail",
    "abstract_per_100w": "ideas and possibilities",
    "laughs_per_100w": "'lol' and 'haha'",
    "profanity_per_100w": "swearing",
}
FEATURES = tuple(FEATURE_LABELS)


def clean_text(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    text = "\n".join(lines)
    text = MDLINK_RE.sub(r"\1", text)
    text = URL_RE.sub("", text)
    text = text.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<")
    return TYPE_TALK_RE.sub(" ", text).strip()


def message_features(text: str) -> dict[str, float] | None:
    """Features of one message, or None if it is too short to say anything."""
    text = clean_text(text)
    words = WORD_RE.findall(text)
    n = len(words)
    if n < 3:
        return None
    first_alpha = next((c for c in text if c.isalpha()), "a")
    sentences = max(1, len(re.findall(r"[.!?]+(\s|$)", text)) + (0 if re.search(r"[.!?]\s*$", text) else 1))
    per100 = 100.0 / n
    caps = sum(1 for w in words if len(w) >= 2 and w.isupper() and w != "I")
    f = {
        "log_words": math.log(n),
        "words_per_sentence": min(60.0, n / sentences),
        "has_exclaim": float("!" in text),
        "has_question": float("?" in text),
        "emoji_per_100w": min(30.0, len(EMOJI_RE.findall(text)) * per100),
        "starts_lowercase": float(first_alpha.islower()),
        "has_ellipsis": float("..." in text or "…" in text),
        "has_parens": float("(" in text),
        "caps_words_per_100w": min(30.0, caps * per100),
        "digits_per_100w": min(30.0, len(re.findall(r"\d+", text)) * per100),
    }
    for key, rx in LEX.items():
        f[f"{key}_per_100w"] = min(40.0, len(rx.findall(text)) * per100)
    return f


def document_features(messages: list[str]) -> tuple[dict[str, float], int] | None:
    """Average message features over a person's messages. Returns (features, usable message count)."""
    rows = [m for m in (message_features(t) for t in messages) if m]
    if not rows:
        return None
    return {k: sum(r[k] for r in rows) / len(rows) for k in FEATURES}, len(rows)
