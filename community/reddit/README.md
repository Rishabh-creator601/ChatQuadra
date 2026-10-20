# Reddit community layer

**Separate from `knowledge/`.** The knowledge base is theory: Jung, cognitive functions, type dynamics. This folder is *observation*: how people who say they are a given type actually write and what they talk about on Reddit. Use it to make the Repliers sound like real people, and to sanity-check the inference signals. It does not override the theory files; where the two disagree, note it rather than silently picking one.

## Contents

| Path | What | In git? |
|---|---|---|
| `scripts/collect.py` | Downloads recent posts and comments from the 16 type subreddits and r/mbti via the Arctic Shift archive | yes |
| `scripts/analyze.py` | Labels items by type, computes style metrics and distinctive vocabulary, writes reading samples | yes |
| `stats/STYLE.md` | Per-type style table (length, punctuation, emoji, hedges, word-category rates) and standouts | yes (aggregates only) |
| `stats/style_metrics.json` | Same numbers, machine-readable, plus z-scores across types. Also `types_flair_only` / `zscores_flair_only`: the same metrics from flair-labelled items only (fewer items, but no visitors) | yes |
| `stats/MODEL.md` | Evaluation of the writing-style model trained by `scripts/train_style_model.py` (maintained by the app session) | yes |
| `stats/distinctive_terms.json` | Words and bigrams most over-used by each type relative to the rest (log-odds, Dirichlet prior) | yes |
| `types/<CODE>.md` | Community profile per type, written in our own words from reading the samples and the stats | yes |
| `raw/` | Verbatim downloads, reading samples, salt, logs | **no** (gitignored) |

Re-run: `python -P community/reddit/scripts/collect.py` then `python -P community/reddit/scripts/analyze.py`.

## Method

1. **Source.** Reddit's own JSON endpoints now require login, so we read the public [Arctic Shift](https://arctic-shift.photon-reddit.com) archive. Up to ~3,000 comments and ~600 posts per type subreddit and ~6,000 comments from r/mbti, newest first, at most two years back.
2. **Privacy.** Usernames are replaced with a salted hash at download time (the salt lives only in `raw/.salt`). Nothing identifying is written to the committed files, and the committed profiles contain no verbatim quotes.
3. **Labels.** An item takes its type from the author's flair when the flair names exactly one type ("INFP 4w5" → INFP; "INTJ or INFJ?" → no label). Otherwise, an item in r/XXXX is labelled XXXX ("sub" label, weaker). Unflaired r/mbti items are dropped. Flair labels are preferred everywhere.
4. **Balance.** Each author contributes at most 25 items per type.
5. **Metrics.** Per item: length, sentence length, punctuation (`!`, `?`, `...`, parentheses), emoji, lowercase style, laughs, and rates per 100 words for hedges, certainty words, I/we/you pronouns, and feeling, logic, social, planning, sensory, abstract and profanity lexicons, plus "type-talk" (MBTI and function jargon).

## Caveats (read before using any number)

- **Self-typed, not verified.** Flair is what people *believe* they are. Mistyping is common, and some types (INFJ, INTJ) are over-claimed online.
- **Topic leakage, at its worst.** Type subreddits are mostly *about* type: identity, relationships with other types, "is this an INFJ thing?". Vocabulary here reflects the setting as much as the person. Do **not** train or tune the inference classifier on these words directly. That is exactly the trap described in `knowledge/05-inference-signals.md`.
- **Reddit is not texting.** Comments are written replies to strangers, often longer and more polished than chat. Use the *relative* differences between types, not the absolute values, when tuning persona pace and length.
- **Who is on Reddit.** Skews young, English-speaking, online, and introverted. E-type subreddits are much smaller, so their numbers are noisier (check `n_authors` in STYLE.md).
- **Visitors skew the small subs.** Only ~15–33% of items in r/ESTJ, r/ESFJ, r/ESTP, r/ESFP and r/ISFP carry that type's flair. The rest include many people asking *about* the type, which inflates question and "you" rates (ESFJ goes from the highest question rate to below average when only flaired authors count). Prefer `types_flair_only` for these five.
- **Small effects.** Most differences between types are modest. A z-score here compares 16 type averages, not individuals.

## Terms and licensing

Reddit posts belong to their authors, and Reddit's Data API terms restrict commercial use and model training without an agreement. This folder is a **research reference**: we keep raw text local, publish only aggregates and our own paraphrased synthesis, and never paste user text into persona prompts. If ChatQuadra becomes a commercial product, review Reddit's current terms (and Arctic Shift's) before relying on this data, or replace it with a licensed or self-collected dataset.
