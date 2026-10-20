"""Train and honestly evaluate a writing-style model for the four type axes.

Each training example is one author's "conversation": a few of their messages averaged into
style features (chatquadra/style_features.py, the same code the app uses). Labels come from
flair or subreddit (see analyze.py). Evaluation splits by AUTHOR, so the model is never tested
on someone it trained on.

Outputs:
  chatquadra/data/style_model.json   numbers only (feature means/scales, weights, eval scores)
  community/reddit/stats/MODEL.md    evaluation report

Usage:  python -P community/reddit/scripts/train_style_model.py
"""
import json
import random
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
sys.path.insert(0, str(PROJECT))
from chatquadra.style_features import FEATURES, document_features  # noqa: E402

RAW, STATS = ROOT / "raw", ROOT / "stats"
OUT = PROJECT / "chatquadra" / "data" / "style_model.json"
TYPES = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
         "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
AXES = [("e_i", 0, "E", "I"), ("s_n", 1, "S", "N"), ("t_f", 2, "T", "F"), ("j_p", 3, "J", "P")]
AUTHOR_CAP = 25
DOCS_PER_AUTHOR = 3
MSGS_PER_DOC = (3, 8)  # like a short chat
C = 0.5
random.seed(11)

import re  # noqa: E402

TYPE_RE = re.compile(r"(?<![A-Z])([IE][NS][TF][JP])(?![A-Z])")


def norm_flair(flair: str):
    found = set(TYPE_RE.findall(unicodedata.normalize("NFKC", flair).upper()))
    return found.pop() if len(found) == 1 else None


def load_items():
    by_author = defaultdict(list)  # (author, type) -> [(text, label)]
    for path in sorted(RAW.glob("*.jsonl")):
        for line in path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:  # a file still being written
                continue
            text = r["text"] if r["kind"] == "comment" else f'{r.get("title", "")}\n\n{r["text"]}'
            flair_type = norm_flair(r["flair"])
            if flair_type:
                t, label = flair_type, "flair"
            elif r["sub"] in TYPES:
                t, label = r["sub"], "sub"
            else:
                continue
            by_author[(r["author_hash"], t)].append((text, label))
    return by_author


def build_docs(by_author):
    docs = []
    for (author, t), items in by_author.items():
        random.shuffle(items)
        items = items[:AUTHOR_CAP]
        made = 0
        i = 0
        while i < len(items) and made < DOCS_PER_AUTHOR:
            k = random.randint(*MSGS_PER_DOC)
            chunk = items[i:i + k]
            i += k
            if len(chunk) < 2:
                break
            feats = document_features([text for text, _ in chunk])
            if not feats or feats[1] < 2:
                continue
            docs.append({
                "author": author, "type": t,
                "flair": all(label == "flair" for _, label in chunk),
                "x": [feats[0][f] for f in FEATURES],
            })
            made += 1
    return docs


def fit(X, y):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    model = LogisticRegression(C=C, class_weight="balanced", max_iter=4000)
    model.fit((X - mu) / sd, y)
    return mu, sd, model


def main():
    docs = build_docs(load_items())
    X = np.array([d["x"] for d in docs])
    groups = np.array([d["author"] for d in docs])
    types = np.array([d["type"] for d in docs])
    is_flair = np.array([d["flair"] for d in docs])
    counts = {t: int((types == t).sum()) for t in TYPES}
    print(f"{len(docs)} documents from {len(set(groups))} authors")

    # --- cross-validated evaluation, split by author ---
    probs = np.zeros((len(docs), 4))
    for train, test in GroupKFold(n_splits=5).split(X, groups=groups):
        for name, idx, first, second in AXES:
            y = np.array([t[idx] == second for t in types[train]], dtype=int)
            if len(set(y)) < 2:
                probs[test, idx] = 0.5
                continue
            mu, sd, m = fit(X[train], y)
            probs[test, idx] = m.predict_proba((X[test] - mu) / sd)[:, 1]

    report = {}
    for name, idx, first, second in AXES:
        y = np.array([t[idx] == second for t in types], dtype=int)
        entry = {"n_first": int((y == 0).sum()), "n_second": int((y == 1).sum())}
        for scope, mask in (("all", np.ones(len(y), bool)), ("flair_only", is_flair)):
            yy, pp = y[mask], probs[mask, idx]
            if len(set(yy)) < 2:
                continue
            entry[scope] = {
                "auc": round(float(roc_auc_score(yy, pp)), 3),
                "balanced_accuracy": round(float(balanced_accuracy_score(yy, pp >= 0.5)), 3),
                "n": int(mask.sum()),
            }
        report[name] = entry

    def type_probs(p):
        out = {}
        for t in TYPES:
            v = 1.0
            for _, idx, first, second in AXES:
                v *= p[idx] if t[idx] == second else 1 - p[idx]
            out[t] = v
        return out

    top1 = top2 = 0
    for p, t in zip(probs, types):
        ranked = sorted(type_probs(p).items(), key=lambda kv: kv[1], reverse=True)
        top1 += ranked[0][0] == t
        top2 += t in (ranked[0][0], ranked[1][0])
    n_types_present = sum(1 for v in counts.values() if v)
    four_letter = {
        "top1": round(top1 / len(docs), 3), "top2": round(top2 / len(docs), 3),
        "chance_top1": round(1 / n_types_present, 3), "chance_top2": round(2 / n_types_present, 3),
    }

    # --- final model on all data ---
    final = {}
    for name, idx, first, second in AXES:
        y = np.array([t[idx] == second for t in types], dtype=int)
        mu, sd, m = fit(X, y)
        coef = m.coef_[0]
        final[name] = {
            "first": first, "second": second,
            "mean": [round(float(v), 5) for v in mu],
            "scale": [round(float(v), 5) for v in sd],
            "coef": [round(float(v), 5) for v in coef],
            "intercept": round(float(m.intercept_[0]), 5),
            "auc": report[name].get("all", {}).get("auc", 0.5),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "features": list(FEATURES), "axes": final, "eval": {"axes": report, "four_letter": four_letter},
        "training": {"documents": len(docs), "authors": int(len(set(groups))), "docs_per_type": counts,
                     "msgs_per_doc": list(MSGS_PER_DOC)},
    }, indent=1), encoding="utf-8")

    write_report(report, four_letter, final, counts, len(docs), len(set(groups)))
    print(json.dumps({"axes": report, "four_letter": four_letter}, indent=1))


def write_report(report, four_letter, final, counts, n_docs, n_authors):
    lines = [
        "# Style model: evaluation", "",
        "Generated by `scripts/train_style_model.py`. One example = one author's 3–8 messages averaged into "
        "writing-style features (`chatquadra/style_features.py`; type jargon and the words introvert/extrovert "
        "are stripped first). Per-axis logistic regression, 5-fold cross-validation **split by author**.", "",
        f"Training set: {n_docs} documents from {n_authors} authors.", "",
        "| Type | documents |", "|---|---|",
        *[f"| {t} | {n} |" for t, n in counts.items()], "",
        "## Per-axis results (AUC 0.5 = chance, 1.0 = perfect)", "",
        "| Axis | AUC (all) | balanced acc. (all) | AUC (flair-labelled only) | n first / second |", "|---|---|---|---|---|",
    ]
    for name, entry in report.items():
        a, f = entry.get("all", {}), entry.get("flair_only", {})
        first, second = final[name]["first"], final[name]["second"]
        lines.append(f"| {first}/{second} | {a.get('auc', '–')} | {a.get('balanced_accuracy', '–')} | "
                     f"{f.get('auc', '–')} | {entry['n_first']} / {entry['n_second']} |")
    lines += ["", "## Four-letter type", "",
              f"Top-1 accuracy {four_letter['top1']:.1%} (chance {four_letter['chance_top1']:.1%}); "
              f"top-2 accuracy {four_letter['top2']:.1%} (chance {four_letter['chance_top2']:.1%}). "
              "Chance assumes uniform types; the data is not uniform, so read this as a rough guide.", "",
              "## Strongest style cues per axis (standardised weights)", ""]
    for name, ax in final.items():
        pairs = sorted(zip(ax["coef"], FEATURES))
        to_first = ", ".join(f"{f} ({c:+.2f})" for c, f in pairs[:4])
        to_second = ", ".join(f"{f} ({c:+.2f})" for c, f in reversed(pairs[-4:]))
        lines.append(f"- **{ax['first']}/{ax['second']}**: toward {ax['second']}: {to_second}. "
                     f"Toward {ax['first']}: {to_first}.")
    lines += ["", "## Caveats", "",
              "- Labels are self-reported and the text is Reddit, mostly from type subreddits. See the README.",
              "- Several cues are still partly topical (feeling/logic/social word rates). Treat the model as a weak, "
              "supporting signal, never as a verdict.", ""]
    STATS.mkdir(exist_ok=True)
    (STATS / "MODEL.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
