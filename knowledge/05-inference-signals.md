# Inference Signals: Reading the User's Typing

**Product rule:** the app never says "you are X". It shows **how the user comes across in the way they type**, as the **two most likely types**, each with a confidence %, plus the evidence behind them.

"Typing" means two things together:
1. **What they write**: the content and style of their messages.
2. **How they type**: keystroke behaviour, collected only with consent and summarised on the device.

---

## 1. Honesty about evidence

| Signal | Strength of evidence | Notes |
|---|---|---|
| Word use vs Big Five traits (Pennebaker, LIWC; Yarkoni 2010) | Moderate, replicated | Strongest for Extraversion, Openness and Neuroticism |
| Text vs MBTI letters (e.g. public MBTI-labelled forum datasets) | Weak to moderate | Models often learn **topic** ("talks about philosophy") instead of personality. E/I and S/N are easiest; T/F and J/P are harder |
| Keystroke dynamics vs personality | Weak, little research | Better studied for identity and emotional state. Use only as a small adjustment |
| MBTI ↔ Big Five (McCrae & Costa 1989) | Solid | E/I ≈ Extraversion, S/N ≈ Openness, T/F ≈ Agreeableness, J/P ≈ Conscientiousness. Useful as a bridge |

So the confidence numbers must be **calibrated and humble**. Early in a conversation, typical top confidence should be low (around 20–35%).

---

## 2. Text signals by preference

Each cue nudges a score. No single cue decides anything.

### E vs I
| Leans E | Leans I |
|---|---|
| Starts new topics, asks many questions, talks about people and plans with others | Answers more than starts, reflects before replying, talks about inner reactions |
| Thinks out loud: several quick messages in a row, self-corrects as they go | Composed single messages, fewer but longer turns |
| More "we", social words (friends, party, call, hang out) | More "I think / I feel", fewer social-event words |
| Exclamation marks, energetic tone | Measured tone, more hedges and qualifications |

### S vs N
| Leans S | Leans N |
|---|---|
| Concrete details, specifics, numbers, sensory words, what happened | Abstractions, metaphors, "what if", meanings, patterns, the future |
| Sequential storytelling ("then… then…") | Jumps between ideas, links unrelated things |
| Practical questions ("how do I…") | Conceptual questions ("why do people…") |

### T vs F
| Leans T | Leans F |
|---|---|
| Arguments, causes, "logically", "objectively", "it makes sense" | Values, people's feelings, "it feels", "it matters to me", "fair to her" |
| Critiques ideas directly, debates | Softens disagreement, checks feelings, thanks and appreciates |
| Solves problems when told about feelings | Empathises first, then helps |

### J vs P
| Leans J | Leans P |
|---|---|
| Plans, deadlines, decisions, "I've decided", tidy closure | Options, "maybe", "we'll see", open endings |
| Organised messages, finished thoughts, correct punctuation | Loose structure, tangents, unfinished thoughts |
| Brings the conversation back to the point | Happy to drift to a new topic |

### Function-level cues (optional, finer-grained)
Use [02-cognitive-functions.md](02-cognitive-functions.md), section "In conversation", to spot dominant-function signatures. For example, Ti shows up as frequent "technically / it depends on what you mean by", Fe as mood-mirroring and inclusive check-ins, Si as "last time / usually / I remember", and Ne as rapid "what if / that reminds me".

---

## 3. Typing-behaviour signals (consent only, weak, capped)

Collected on the device as **aggregates per message**: no raw keys and no deleted text ever leave the device.

| Metric | Possible lean | Cap |
|---|---|---|
| Reply latency (time before they start typing) | Short → E / P (reactive). Long → I (reflective) | ±0.05 per axis |
| Pause before sending, after typing is done | Long review → J / I. Instant send → P / E | ±0.05 |
| Backspace / edit ratio | High editing → J (polish) or I (care). Low → P / E | ±0.03 |
| Message bursts (several sends in a row) | E / P (thinking out loud) | ±0.05 |
| Typing-indicator start/stop cycles (hesitation) | I / F (careful wording) | ±0.03 |

Behaviour **never** outweighs text. These adjustments are capped and always shown as "minor signal" in the evidence panel.

---

## 4. From signals to top-2 types

1. **Per-axis score.** Every N user messages, the text analyser returns for each axis `score ∈ [-1, +1]` (for example −1 = I, +1 = E), plus `confidence ∈ [0, 1]` and evidence quotes. Behaviour adds a small capped nudge.
2. **Running estimate.** Keep a confidence-weighted average per axis, with mild recency weighting and confidence that grows with word count.
3. **Axis probability.** Convert to `P(E)`, `P(N)`, `P(F)`, `P(P)` with a logistic function that is deliberately *flattened* (temperature > 1) so we don't sound over-certain.
4. **16-type distribution.** `P(type) = Π` of its four letter probabilities (assumes the axes are independent). Optionally re-weight using function-level cues (for example a strong Ti signature boosts INTP/ISTP and ENTP/ESTP).
5. **Top 2.** Sort and show the top two types with their probabilities rounded to whole %, each with 2–3 evidence quotes from the user's own messages and the key behaviour signals.
6. **Gating.** Show nothing until there are about 150 words. Until then, show "still getting to know how you come across". Always offer "Doesn't sound like me" feedback, which we keep as a calibration label.

Example output shape:
```json
{
  "top_types": [
    { "type": "INFP", "nickname": "The Poet", "confidence": 0.31,
      "why": ["values language: \"it just didn't feel right to me\"",
              "lots of what-ifs and tangents", "long pauses before sending (minor)"] },
    { "type": "INFJ", "nickname": "The Seer", "confidence": 0.22,
      "why": ["focus on what people really meant", "reflective, composed messages"] }
  ],
  "axes": { "E_I": -0.42, "S_N": 0.55, "T_F": 0.38, "J_P": 0.06 },
  "words_analysed": 612,
  "basis": "how you come across in your typing — not a diagnosis"
}
```

---

## 5. Pitfalls to guard against
- **Topic leakage:** a user talking about coding is not necessarily T, and one talking about feelings is not necessarily F. Score *how* they talk, not *what about*.
- **Mirroring:** users adapt to the Replier's style. Chatting with an ENFP Replier may make anyone sound more N/P. Store the persona with each snapshot and correct for it in evals.
- **Mood vs trait:** a stressed user may look like their inferior function (see the grip in [03-type-dynamics.md](03-type-dynamics.md)). Use recency weighting gently.
- **Language and culture:** cues like exclamation marks or emoji use vary across cultures and age groups. Calibrate per language before scoring.
