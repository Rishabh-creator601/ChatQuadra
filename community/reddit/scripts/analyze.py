"""Turn the raw Reddit downloads into per-type style statistics and reading samples.

Labels: an item gets a type from its author's flair when the flair names exactly one
four-letter type ("flair" label). Otherwise, items in a type subreddit get that
subreddit's type ("sub" label, weaker: visitors of other types post there too).
Unflaired r/mbti items are dropped. Each author contributes at most AUTHOR_CAP items
per type so prolific posters don't dominate.

Outputs (committable, aggregates only):  stats/style_metrics.json, stats/STYLE.md,
                                         stats/distinctive_terms.json
Outputs (gitignored, verbatim text):      raw/samples/<TYPE>.txt

Usage:  python -P community/reddit/scripts/analyze.py
"""
import json
import math
import random
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW, STATS = ROOT / "raw", ROOT / "stats"
TYPES = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
         "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
AUTHOR_CAP = 25
MIN_WORDS = 3
random.seed(7)

TYPE_RE = re.compile(r"(?<![A-Z])([IE][NS][TF][JP])(?![A-Z])")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
MDLINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
WORD_RE = re.compile(r"[A-Za-z']+")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
TYPE_TALK_RE = re.compile(
    r"\b([IE][NS][TF][JP]s?|[IE]N[TF]Ps?|[TFSN][ie]|[TFSN][ie]-[TFSN][ie]|mbti|enneagram|"
    r"\dw\d|cognitive functions?|dom|aux|tert|inferior|grip|socionics|polr|"
    r"sefi|seti|feni|neti|tini|sifi)\b"
    # Socionics type codes (LSE, EII, SLE, ...): upper-case only, or they'd match "the", "are".
    r"|(?-i:\b(?:[LSEI][LSEI][IE]|[LSEI][NSTF][IE]|[NSTF][LE][IE]|[ILE]E[IE])\b)", re.I)
# Moderator notices and recurring mod threads: not anyone's personal writing.
MOD_RE = re.compile(r"(your )?(post|comment|post/comment) (has been|was) removed|"
                    r"monthly discussion thread|automod|I am a bot", re.I)
# Rough English check: share of words that are very common English function words.
ENGLISH = set("""the a an and or but to of in on at for with is are was were be it this that i you he she
they we my your not do have has had so just like what if me can would will about there all""".split())


def lexicon(*phrases: str) -> re.Pattern:
    return re.compile(r"\b(" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in phrases) + r")\b", re.I)


LEX = {
    "hedges": lexicon("maybe", "perhaps", "probably", "i think", "i guess", "kind of", "kinda",
                      "sort of", "idk", "i don't know", "i dont know", "might", "possibly",
                      "seems", "i feel like", "not sure"),
    "certainty": lexicon("definitely", "obviously", "clearly", "always", "never", "absolutely",
                         "certainly", "of course", "no doubt", "100%", "for sure"),
    "i_words": lexicon("i", "me", "my", "mine", "myself", "i'm", "im", "i've", "i'd", "i'll"),
    "we_words": lexicon("we", "us", "our", "ours", "ourselves", "we're", "let's"),
    "you_words": lexicon("you", "your", "yours", "yourself", "you're", "youre", "u", "ur"),
    "feeling": lexicon("feel", "feels", "feeling", "feelings", "felt", "love", "hurt", "sad",
                       "happy", "heart", "care", "emotional", "emotions", "emotion", "anxious",
                       "anxiety", "lonely", "cry", "crying", "scared", "afraid", "hug"),
    "logic": lexicon("logic", "logical", "logically", "reason", "reasoning", "therefore",
                     "technically", "evidence", "efficient", "objectively", "objective",
                     "makes sense", "rational", "analyze", "analysis", "data", "system"),
    "social": lexicon("friend", "friends", "people", "family", "party", "hang out", "together",
                      "mom", "dad", "partner", "boyfriend", "girlfriend", "bf", "gf", "husband",
                      "wife", "coworkers", "group"),
    "planning": lexicon("plan", "plans", "planning", "goal", "goals", "deadline", "schedule",
                        "organize", "organized", "routine", "list", "future", "career"),
    "sensory": lexicon("look", "looks", "taste", "food", "eat", "music", "sound", "color",
                       "clothes", "outfit", "gym", "body", "smell", "touch", "beautiful"),
    "abstract": lexicon("meaning", "concept", "theory", "idea", "ideas", "possibility",
                        "possibilities", "pattern", "patterns", "philosophy", "universe",
                        "existential", "imagine", "what if", "abstract"),
    "laughs": lexicon("lol", "lmao", "lmfao", "haha", "hahaha", "hehe", "rofl", "xd"),
    "profanity": lexicon("fuck", "fucking", "fucked", "shit", "damn", "hell", "ass", "bitch",
                         "crap", "wtf"),
}


def norm_flair(flair: str) -> str | None:
    found = set(TYPE_RE.findall(unicodedata.normalize("NFKC", flair).upper()))
    return found.pop() if len(found) == 1 else None


def clean_text(text: str) -> str:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith(">")]
    text = "\n".join(lines)
    text = MDLINK_RE.sub(r"\1", text)
    text = URL_RE.sub("", text)
    return text.replace("&amp;", "&").replace("&gt;", ">").replace("&lt;", "<").strip()


def is_english(text: str) -> bool:
    words = [w.lower() for w in WORD_RE.findall(text)]
    return len(words) < 8 or sum(w in ENGLISH for w in words) / len(words) >= 0.15


def metrics(text: str) -> dict | None:
    words = WORD_RE.findall(text)
    n = len(words)
    if n < MIN_WORDS:
        return None
    letters = [c for c in text if c.isalpha()]
    first_alpha = next((c for c in text if c.isalpha()), "a")
    sentences = max(1, len(re.findall(r"[.!?]+(\s|$)", text)) + (0 if re.search(r"[.!?]\s*$", text) else 1))
    per100 = 100.0 / n
    caps = sum(1 for w in words if len(w) >= 2 and w.isupper() and not TYPE_RE.fullmatch(w) and w != "I")
    m = {
        "words": n,
        "words_per_sentence": n / sentences,
        "emoji_per_100w": len(EMOJI_RE.findall(text)) * per100,
        "has_emoji": float(bool(EMOJI_RE.search(text))),
        "has_exclaim": float("!" in text),
        "has_question": float("?" in text),
        "starts_lowercase": float(first_alpha.islower()),
        "all_lowercase": float(n >= 5 and not any(c.isupper() for c in letters)),
        "has_ellipsis": float("..." in text or "…" in text),
        "has_parens": float("(" in text),
        "multi_paragraph": float("\n\n" in text.strip()),
        "caps_words_per_100w": caps * per100,
        "digits_per_100w": len(re.findall(r"\d+", text)) * per100,
        "type_talk_per_100w": len(TYPE_TALK_RE.findall(text)) * per100,
    }
    for key, rx in LEX.items():
        m[f"{key}_per_100w"] = len(rx.findall(text)) * per100
    return m


def load() -> list[dict]:
    rows = []
    for path in sorted(RAW.glob("*.jsonl")):
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            body = r["text"] if r["kind"] == "comment" else f'{r.get("title", "")}\n\n{r["text"]}'
            r["clean"] = clean_text(body)
            if MOD_RE.search(r["clean"]) or not is_english(r["clean"]):
                continue
            flair_type = norm_flair(r["flair"])
            if flair_type:
                r["type"], r["label"] = flair_type, "flair"
            elif r["sub"] in TYPES:
                r["type"], r["label"] = r["sub"], "sub"
            else:
                continue
            rows.append(r)
    return rows


def cap_authors(rows: list[dict]) -> list[dict]:
    random.shuffle(rows)
    per = Counter()
    kept = []
    for r in rows:
        key = (r["type"], r["author_hash"])
        if per[key] < AUTHOR_CAP:
            per[key] += 1
            kept.append(r)
    return kept


def aggregate(rows: list[dict]) -> dict:
    by_type = defaultdict(list)
    for r in rows:
        if r["m"]:
            by_type[r["type"]].append(r)
    out = {}
    for t in TYPES:
        items = by_type.get(t, [])
        if not items:
            continue
        keys = items[0]["m"].keys()
        agg = {k: statistics.fmean(i["m"][k] for i in items) for k in keys}
        agg["median_words"] = statistics.median(i["m"]["words"] for i in items)
        agg["n_items"] = len(items)
        agg["n_authors"] = len({i["author_hash"] for i in items})
        agg["n_flair_items"] = sum(1 for i in items if i["label"] == "flair")
        agg["n_comments"] = sum(1 for i in items if i["kind"] == "comment")
        out[t] = agg
    return out


def zscores(agg: dict) -> dict:
    keys = [k for k in next(iter(agg.values())) if not k.startswith("n_")]
    z = {t: {} for t in agg}
    for k in keys:
        vals = [agg[t][k] for t in agg]
        mu, sd = statistics.fmean(vals), statistics.pstdev(vals) or 1.0
        for t in agg:
            z[t][k] = (agg[t][k] - mu) / sd
    return z


STOP = set("""a an the and or but if then so of to in on at for with by from as is are was were be been being
it its it's this that these those there here i me my you your he she they them we us our his her their what which
who whom how why when where not no yes do does did done have has had just like can could would should will
about all any some more most very also than too only out up down over into get got im i'm dont don't it's
youre you're thats that's really one even much way thing things lot because know think people""".split())


def distinctive_terms(rows: list[dict], top: int = 40) -> dict:
    """Log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi & Quinn 2008)."""
    counts = {t: Counter() for t in TYPES}
    for r in rows:
        toks = [w.lower() for w in WORD_RE.findall(TYPE_TALK_RE.sub(" ", r["clean"]))]
        toks = [w for w in toks if len(w) > 2 and w not in STOP]
        counts[r["type"]].update(toks)
        counts[r["type"]].update(f"{a} {b}" for a, b in zip(toks, toks[1:]))
    total = Counter()
    for c in counts.values():
        total.update(c)
    vocab = {w for w, n in total.items() if n >= 15}
    a0 = sum(total[w] for w in vocab)
    alpha = {w: total[w] / a0 * 1000 for w in vocab}
    a_sum = sum(alpha.values())
    out = {}
    for t in TYPES:
        ci = counts[t]
        ni = sum(ci[w] for w in vocab)
        nj = a0 - ni
        if ni == 0:
            continue
        scores = []
        for w in vocab:
            yi, yj, aw = ci[w], total[w] - ci[w], alpha[w]
            d = (math.log((yi + aw) / (ni + a_sum - yi - aw))
                 - math.log((yj + aw) / (nj + a_sum - yj - aw)))
            var = 1 / (yi + aw) + 1 / (yj + aw)
            scores.append((d / math.sqrt(var), w, yi))
        scores.sort(reverse=True)
        out[t] = [{"term": w, "z": round(s, 2), "count": n} for s, w, n in scores[:top] if n >= 5]
    return out


LABELS = {
    "median_words": "median words", "words_per_sentence": "words/sentence",
    "emoji_per_100w": "emoji/100w", "has_exclaim": "% with !", "has_question": "% with ?",
    "starts_lowercase": "% lowercase start", "all_lowercase": "% all lowercase",
    "has_ellipsis": "% with ...", "laughs_per_100w": "lol/haha /100w",
    "hedges_per_100w": "hedges/100w", "certainty_per_100w": "certainty/100w",
    "i_words_per_100w": "I-words/100w", "we_words_per_100w": "we-words/100w",
    "you_words_per_100w": "you-words/100w", "feeling_per_100w": "feeling/100w",
    "logic_per_100w": "logic/100w", "social_per_100w": "social/100w",
    "planning_per_100w": "planning/100w", "sensory_per_100w": "sensory/100w",
    "abstract_per_100w": "abstract/100w", "profanity_per_100w": "profanity/100w",
    "type_talk_per_100w": "type-talk/100w", "has_parens": "% with ( )",
    "caps_words_per_100w": "CAPS/100w",
}
PCT = {k for k in LABELS if k.startswith("has_") or k in {"starts_lowercase", "all_lowercase"}}


def fmt(k: str, v: float) -> str:
    return f"{v * 100:.0f}%" if k in PCT else f"{v:.1f}" if v < 100 else f"{v:.0f}"


def write_markdown(agg: dict, z: dict, terms: dict) -> None:
    cols = ["median_words", "words_per_sentence", "has_exclaim", "has_question", "emoji_per_100w",
            "starts_lowercase", "has_ellipsis", "laughs_per_100w", "hedges_per_100w",
            "certainty_per_100w", "feeling_per_100w", "logic_per_100w", "social_per_100w",
            "abstract_per_100w", "sensory_per_100w", "profanity_per_100w", "type_talk_per_100w"]
    lines = ["# Reddit style metrics by type", "",
             "Generated by `scripts/analyze.py`. Means per item (comment or post) after capping each author at "
             f"{AUTHOR_CAP} items per type. See [README](../README.md) for caveats before using these numbers.", "",
             "## Sample sizes", "", "| Type | items | authors | flair-labelled | comments |", "|---|---|---|---|---|"]
    for t, a in agg.items():
        lines.append(f"| {t} | {a['n_items']} | {a['n_authors']} | {a['n_flair_items']} | {a['n_comments']} |")
    lines += ["", "## Metrics", "", "| Type | " + " | ".join(LABELS[c] for c in cols) + " |",
              "|---" * (len(cols) + 1) + "|"]
    for t, a in agg.items():
        lines.append(f"| {t} | " + " | ".join(fmt(c, a[c]) for c in cols) + " |")
    lines += ["", "## What stands out per type", "",
              "Largest deviations from the 16-type average (z-score across type means; |z| ≥ 1 shown).", ""]
    for t in agg:
        hi = sorted(((v, k) for k, v in z[t].items() if k in LABELS and v >= 1), reverse=True)[:5]
        lo = sorted((v, k) for k, v in z[t].items() if k in LABELS and v <= -1)[:5]
        hi_s = ", ".join(f"{LABELS[k]} (+{v:.1f})" for v, k in hi) or "none"
        lo_s = ", ".join(f"{LABELS[k]} ({v:.1f})" for v, k in lo) or "none"
        words = ", ".join(x["term"] for x in terms.get(t, [])[:15])
        lines += [f"**{t}**: higher: {hi_s}. Lower: {lo_s}.", f"Distinctive words: {words}", ""]
    (STATS / "STYLE.md").write_text("\n".join(lines), encoding="utf-8")


def write_samples(rows: list[dict], per_type: int = 140) -> None:
    out_dir = RAW / "samples"
    out_dir.mkdir(exist_ok=True)
    for t in TYPES:
        pool = [r for r in rows if r["type"] == t and r["kind"] == "comment" and r["m"]
                and 12 <= r["m"]["words"] <= 180]
        chosen, authors = [], set()
        # One comment per author: flair-labelled first (top-scored half, then random), then
        # subreddit-labelled to fill up when few flaired authors exist (small E-type subs).
        for label in ("flair", "sub"):
            part = sorted((r for r in pool if r["label"] == label), key=lambda r: -(r["score"] or 0))
            for r in part[: per_type // 2] + random.sample(part, len(part)):
                if len(chosen) >= per_type:
                    break
                if r["author_hash"] not in authors:
                    authors.add(r["author_hash"])
                    chosen.append(r)
        titles = [r for r in rows if r["type"] == t and r["kind"] == "post"]
        titles = random.sample(titles, min(40, len(titles)))
        with (out_dir / f"{t}.txt").open("w", encoding="utf-8") as f:
            f.write(f"# {t}: {len(chosen)} comments (label, score, subreddit), then post titles\n\n")
            for r in chosen:
                f.write(f"--- [{r['label']}|{r['score']}|r/{r['sub']}]\n{r['clean']}\n\n")
            f.write("=== POST TITLES\n")
            for r in titles:
                f.write(f"- [r/{r['sub']}] {r.get('title', '')}\n")


def main() -> None:
    STATS.mkdir(exist_ok=True)
    rows = cap_authors(load())
    for r in rows:
        r["m"] = metrics(r["clean"])
    rows = [r for r in rows if r["m"]]
    agg = aggregate(rows)
    z = zscores(agg)
    # Flair-only view: excludes visitors writing *about* a type in its subreddit. Fewer items,
    # but cleaner for small subs (e.g. only ~15% of r/ESTJ items are ESTJ-flaired).
    agg_flair = aggregate([r for r in rows if r["label"] == "flair"])
    z_flair = zscores(agg_flair)
    terms = distinctive_terms(rows)
    (STATS / "style_metrics.json").write_text(json.dumps(
        {"author_cap": AUTHOR_CAP, "types": agg, "zscores": z,
         "types_flair_only": agg_flair, "zscores_flair_only": z_flair}, indent=1), encoding="utf-8")
    (STATS / "distinctive_terms.json").write_text(json.dumps(terms, indent=1), encoding="utf-8")
    write_markdown(agg, z, terms)
    write_samples(rows)
    print(f"{len(rows)} items analysed across {len(agg)} types")


if __name__ == "__main__":
    main()
