"""Writing-style reading of the user, from a small model trained on Reddit data.

The model (chatquadra/data/style_model.json) is trained by
community/reddit/scripts/train_style_model.py and evaluated by author-split cross-validation.
It is a weak signal: each axis is trusted in proportion to how well it did in evaluation.
Scoring is plain Python (no numpy/sklearn at runtime).
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from .schemas import AxisReading, TextAnalysis
from .style_features import FEATURE_LABELS, FEATURES, document_features
from .typedata import AXES

MODEL_PATH = Path(__file__).resolve().parent / "data" / "style_model.json"
# Messages at which the style evidence counts fully.
FULL_MESSAGES = 6


@lru_cache(maxsize=1)
def load_model() -> dict | None:
    if not MODEL_PATH.exists():
        return None
    model = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
    if model.get("features") != list(FEATURES):
        return None  # trained on a different feature set; retrain
    return model


def reliability(auc: float) -> float:
    """Map evaluation AUC (0.5 chance .. 1.0 perfect) to a 0..1 trust weight."""
    return max(0.0, min(1.0, (auc - 0.5) * 2))


def style_reading(messages: list[str]) -> tuple[TextAnalysis, list[str]] | None:
    """Return a TextAnalysis built only from writing style, plus plain-language notes."""
    model = load_model()
    if not model:
        return None
    doc = document_features(messages)
    if not doc:
        return None
    feats, n_used = doc
    x = [feats[f] for f in FEATURES]
    amount = min(1.0, n_used / FULL_MESSAGES)

    readings: dict[str, AxisReading] = {}
    notes: list[str] = []
    for name, ax in model["axes"].items():
        z = [(v - m) / s for v, m, s in zip(x, ax["mean"], ax["scale"])]
        contrib = [c * zi for c, zi in zip(ax["coef"], z)]
        logit = ax["intercept"] + sum(contrib)
        p = 1 / (1 + math.exp(-logit))
        lean = 2 * p - 1  # -1 first letter .. +1 second letter
        trust = reliability(ax["auc"])
        target = ax["second"] if lean > 0 else ax["first"]
        # The two features pushing hardest toward the leaning side, in plain words.
        ranked = sorted(range(len(FEATURES)), key=lambda i: contrib[i] * (1 if lean > 0 else -1), reverse=True)
        evidence = []
        for i in ranked[:2]:
            if contrib[i] * lean <= 0:
                break
            more = "more" if z[i] > 0 else "less"
            evidence.append(f"writing style: {more} {FEATURE_LABELS[FEATURES[i]]} than most")
        readings[name] = AxisReading(lean=round(lean, 3), confidence=round(trust * amount, 3), evidence=evidence)
        if trust >= 0.1 and abs(lean) >= 0.15 and evidence:
            notes.append(f"Your writing style leans {target}: {evidence[0].split(': ', 1)[1]}.")

    analysis = TextAnalysis(
        **readings,
        function_cues=[],
        impression="This reading comes from your writing style alone (length, punctuation, word choice), "
        "which says only a little about personality.",
        persona_note="",
    )
    return analysis, notes


def blend(llm: TextAnalysis, style: TextAnalysis) -> TextAnalysis:
    """Combine Claude's reading with the style model, weighting each axis by its confidence."""
    merged = {}
    for name, _, _ in AXES:
        a, b = getattr(llm, name), getattr(style, name)
        wa, wb = max(a.confidence, 1e-3), b.confidence * 0.5  # the style model is a supporting voice
        lean = (a.lean * wa + b.lean * wb) / (wa + wb)
        merged[name] = AxisReading(lean=round(lean, 3), confidence=a.confidence, evidence=a.evidence)
    return llm.model_copy(update=merged)
