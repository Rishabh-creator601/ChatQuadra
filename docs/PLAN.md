# ChatQuadra — Product & Technical Plan

> Status: planning only. No UI is built yet. This document is the reference for building each part separately.

---

## 1. The core idea

The user sits "across the table" from a person who has one of the 16 personality types. That person (the **Replier**) talks like a real human with that type: their own opinions, mood, pace, quirks and texting habits. It should never feel like a chatbot answering questions.

While they talk, the app quietly builds an estimate of the **User's** own type from what they write and how they type. The user can open that estimate whenever they like.

Two roles throughout the system:

| Role | Who | Notes |
|---|---|---|
| **User** | The real person | Has a display name; their type is *unknown* and inferred over time |
| **Replier** | An AI persona | Has a human name, one of 16 types, a backstory, a mood, and a memory of this user |

### What makes it feel "human, not chatbot"
1. **Timing.** The Replier "reads" the message, pauses, types (with a typing indicator that can stop and restart), and sometimes sends 2–3 short messages in a row instead of one block.
2. **Voice.** No bullet lists, no "Great question!", no offers of help. Short, casual, imperfect. They have opinions and can disagree.
3. **Initiative.** They ask things back, change the subject, bring up their own day, and remember what the user said last time.
4. **Presence.** Each reply carries an emotion or expression, so the later UI can show a face or avatar reacting rather than a chat log.
5. **Type-authentic behaviour.** An INTJ and an ESFP should differ in *what* they notice, *how* they argue, *how fast* they answer and *how much* they write, not just in vocabulary.

---

## 2. Brand / legal guardrails (decide early)

- **16Personalities** (NERIS Analytics) and **MBTI / Myers-Briggs** (The Myers-Briggs Company) are trademarks. Their illustrations, the type nicknames ("Architect", "Logician", "Mediator"…), the "Analysts / Diplomats / Sentinels / Explorers" group names and their test questions are their IP.
- **Plan:** take *inspiration* from their visual style (clean, colourful, friendly, illustrated characters) but use **our own art, names and copy**. Use the four-letter codes (INTJ, ENFP…), which are generic, and our own nicknames and group names.
- **Decided:** our own nicknames and groups are in [`knowledge/04-nicknames-and-groups.md`](../knowledge/04-nicknames-and-groups.md). Groups: **The Minds** (NT), **The Hearts** (NF), **The Anchors** (SJ), **The Sparks** (SP). Examples: INTJ *The Cartographer*, INFP *The Poet*, ESTJ *The Steward*, ESFP *The Showstopper*. Run a trademark search before launch.
- **No content from 16personalities.com** is scraped or copied. Persona knowledge comes from Jung (public domain, 1923 translation) and our own synthesis (see section 9).
- Do not scrape or reuse their test items. If we add a questionnaire, write our own or use open instruments (such as the IPIP Big Five items, which are public domain).

---

## 3. Feature list

### MVP
| # | Feature | Description |
|---|---|---|
| F1 | Persona gallery | Choose 1 of 16 Repliers (name, type, short bio, art) |
| F2 | Human-like conversation | Persona Engine and Human Behaviour Layer (sections 5 and 6) |
| F3 | Typing realism | Typing indicator, read delay, message bursts, occasional pause or restart |
| F4 | Emotion per message | Each reply has an `emotion` and `expression` for the avatar |
| F5 | User type inference | Estimated from the user's **typing** (what they write and how they type). Output is the **two most likely types**, each with a confidence %. It is never presented as the user's "actual" type |
| F6 | "How you come across" panel | Top-2 types with nickname and confidence %, the 4 axis bars, and *why* (quoted evidence and minor typing-behaviour signals). Includes a "doesn't sound like me" button |
| F7 | Consent | Opt-in for typing-behaviour signals, with a plain explanation |

### Later
- **Long-term memory** per User–Replier pair ("you said your exam was Friday, how did it go?")
- **Persona inner life**: a daily mood and a small "what happened today" seed so conversations differ
- **Compatibility insight**: how the user's inferred type tends to interact with the chosen Replier's type
- **Group table**: 2–3 Repliers in one conversation who react to each other
- **Optional short questionnaire** (our own items) to calibrate the inference and give us ground truth
- **Voice mode** (speech in and out), which adds prosody as a signal

---

## 4. System architecture

```
┌──────────────────────────── Client (UI later) ────────────────────────────┐
│  Conversation view (presence, not chat)    Typing telemetry collector     │
│  • plays Replier messages with delays      • keydown timing, backspaces,  │
│  • avatar expression from `emotion`          pauses, edit ratio, latency  │
│                                            • aggregated client-side; no   │
│                                              raw keystrokes leave device  │
└───────────────┬───────────────────────────────────────┬──────────────────┘
                │ user message + typing summary          │
                ▼                                        │
┌─────────────────────────── Backend (API) ──────────────┴──────────────────┐
│  Conversation Orchestrator                                                │
│   ├─► Persona Engine ──► Claude (persona reply, structured JSON)          │
│   ├─► Human Behaviour Layer (timing plan: read delay, typing time,        │
│   │                          bursts, pauses)                              │
│   ├─► Personality Inference (async, every N user messages)                │
│   │     ├─ Text analyser ──► Claude (axis scores + evidence, JSON)        │
│   │     ├─ Behaviour analyser (heuristics on typing summary)              │
│   │     └─ Aggregator (running per-axis estimate with confidence)         │
│   └─► Memory Service (facts about the user, per Replier)                  │
│                                                                           │
│  Storage: Postgres (users, sessions, messages, inference snapshots,       │
│           memories, aggregated typing stats)                              │
└───────────────────────────────────────────────────────────────────────────┘
```

**Stack (updated):** the shared engine is now **Python** (official `anthropic` SDK, Pydantic), because one of the two apps is Streamlit. The product ships as a **Streamlit app** on Streamlit Community Cloud (the separate web app was cancelled). Postgres comes later for persistence. Full build plan: [APP_PLAN.md](APP_PLAN.md).

---

## 5. Persona Engine (the Replier)

### 5.1 Persona spec (one file per persona: `personas/<code>.yaml`)
Every persona is data, not code, so we can tune all 16 without changing logic.

```yaml
code: INFP
name: "Mira"
age: 24
life: "Illustrator, lives with a cat named Pickle, writes poetry nobody reads"
cognitive_stack: [Fi, Ne, Si, Te]        # dominant → inferior
big_five_tendencies: { O: high, C: low-mid, E: low, A: high, N: mid-high }
voice:
  avg_message_length: short-medium
  burstiness: high            # often sends 2-3 messages in a row
  emoji: occasional, soft (🥲 ✨)
  punctuation: lowercase, trailing "..."
  humour: whimsical, self-deprecating
  directness: low — hints rather than states
values: [authenticity, creativity, kindness]
in_conversation:
  notices: feelings, meaning, what is left unsaid
  asks_about: the user's inner experience, dreams
  avoids: blunt criticism, conflict, small-talk logistics
  when_disagreeing: gentle, "hmm i see it a bit differently..."
under_stress: "Te grip: suddenly critical, cold, over-organising"
quirks: ["goes off on tangents about stories", "remembers tiny details"]
pace: { read_delay: slow, typing_wpm: 38, reply_latency_variance: high }
```

### 5.2 Prompt structure (built for prompt caching)
Order matters, because caching matches a prefix and anything that changes breaks the cache from that point on.

1. **System (frozen, cached):** global "be a human, not an assistant" rules, then the persona spec, then the output format.
2. **Messages (append-only):** the conversation history. Never edit earlier turns.
3. **Per-turn context** (time of day, the persona's current mood, recalled memories): appended as a **mid-conversation system message**, not placed in the top-level system prompt, so the cached prefix stays valid.

Core "human" rules for the system prompt (draft):
- Text like a person on a phone. Usually 1–3 short messages. No lists, headings or markdown.
- You have your own life, opinions and moods. Don't be endlessly agreeable or helpful.
- Ask questions back when *you'd* be curious, not as a reflex.
- Let your type show through what you notice and value, not by naming your type.
- **Honesty rule:** if the user sincerely asks whether they're talking to an AI, say so truthfully and gently, then carry on in character if they want. This is required, not optional.
- Safety: if the user seems in real distress, step partly out of role and point them to real help.

### 5.3 Reply output (structured JSON)
```json
{
  "messages": ["omg wait", "that's actually such a good point..."],
  "emotion": "delighted",            // enum, drives avatar
  "intensity": 0.7,
  "wants_to_continue": true,          // may send a follow-up after a pause
  "memory_candidates": ["user has an exam on Friday"]
}
```
We get this with structured outputs (`output_config.format` plus a JSON schema), so the backend never parses free text.

### 5.4 Model choice
- **Persona replies:** `claude-opus-5-5`, adaptive thinking, effort `low` to `medium` (chat does not need deep reasoning; tune with evals). Keep the server-side **refusal fallback** enabled.
- **Inference / text analysis:** also `claude-opus-5-5` at `low` effort by default. A cheaper model (for example `claude-haiku-5-5`) is an option if cost matters. That is a cost/quality decision for you, and we should measure it before switching.
- **Streaming:** less important here than in a chatbot. We *want* a realistic delay, so the reply is generated during the "reading / typing" animation, which hides LLM latency. We still stream server-side so long outputs don't time out.

---

## 6. Human Behaviour Layer (timing and presence)

Deterministic code, not the LLM, turns a reply into a **delivery plan**:

```
read_delay  = f(user_msg_length, persona.pace.read_delay) + jitter
for each message in reply.messages:
    typing_time = len(message) / persona.typing_wpm  (+ jitter)
    maybe: typing indicator starts → stops → restarts (hesitation), more
           likely for low-directness types or emotional content
    gap_between_bursts = small random
optional: follow-up message after 5–20 s if wants_to_continue
```

Rules of thumb per temperament (initial guesses, to tune):
- **Extraverts:** faster first response, more bursts, more follow-ups.
- **Introverts:** longer read delay, fewer but more considered messages.
- **Feeling types:** more emoji and softeners. **Thinking types:** fewer, more direct.
- **Perceivers:** more tangents and hesitations. **Judgers:** tidier, more complete messages.

If the user types while the Replier is "typing", the Replier can stop and wait, as people do.

---

## 7. Personality Inference (classifying the User)

### 7.1 Be honest about what's possible
- Inferring type from text is a **probabilistic guess**. Research on predicting personality from language (for example Pennebaker's LIWC work and Yarkoni's 2010 blogger study) finds real but **modest** correlations, which are stronger for Big Five traits than for MBTI letters.
- Keystroke dynamics are well studied for *identity* and *emotional state*. Their link to personality type is **weak**. Treat them as a small signal, mostly for E/I and J/P.
- Product framing: "Here's how you come across in this conversation", not "This is your type". Show confidence levels and let the user disagree.

### 7.2 Signals
| Source | Examples | Mostly informs |
|---|---|---|
| **Content** (LLM) | Topics, abstract vs concrete language, values talk, logic vs feeling framing, planning vs open-ended talk | S/N, T/F, J/P |
| **Style** (computed) | Message length, pronoun use (I vs we), hedges, emoji and exclamation marks, question rate | E/I, T/F |
| **Behaviour** (client) | Typing speed, backspace/edit ratio, pause before send, response latency, whether they start new topics | E/I, J/P (weak) |

### 7.3 Pipeline (details in [`knowledge/05-inference-signals.md`](../knowledge/05-inference-signals.md))
1. Every N user messages (for example 3), run the **text analyser** asynchronously, so it never delays the Replier.
2. It returns structured JSON for each axis: `score` (−1…+1), `confidence` (0…1) and short `evidence` quotes from the user's own messages.
3. The **aggregator** keeps a running estimate per axis, a confidence-weighted average where recent evidence counts a little more and confidence grows with the amount of text. Behaviour signals add a small, capped adjustment.
4. **Axes to types:** convert each axis to a probability (deliberately flattened so we don't over-claim), multiply the four letter probabilities to get a distribution over all 16 types, and optionally re-weight using dominant-function cues.
5. **Show the top 2 types** with their confidence %, each with 2–3 evidence quotes. The framing is always "how you come across in your typing", not "your type".
6. A snapshot is stored after each run, so the UI can show the estimate changing over time.
7. Only show results once minimum evidence is reached (for example 150+ words). Before that, show "still getting to know how you come across".

### 7.4 Evaluation
- Build a small labelled eval set: conversations by people who know their type (from our questionnaire or self-report), plus synthetic users played by Claude with known types.
- Measure per-axis accuracy and how confidence relates to accuracy. The goal is calibrated confidence, not just a confident answer.
- Watch for a known trap: models often pick up on **topic** ("talks about philosophy" = N) rather than personality. The eval should include off-topic conversations.

---

## 8. Data model (first draft)

```
User(id, display_name, created_at, telemetry_consent)
Persona(code, name, spec_version)                    -- loaded from YAML
Session(id, user_id, persona_code, started_at, persona_mood)
Message(id, session_id, role[user|replier], text, emotion, created_at,
        delivery_plan_json)
TypingSummary(message_id, wpm, backspace_ratio, pause_before_send_ms,
              latency_ms)                            -- aggregated only
InferenceSnapshot(id, user_id, session_id, axes_json, overall_type,
                  confidence, evidence_json, created_at)
Memory(id, user_id, persona_code, fact, salience, created_at)
```

---

## 9. Psychology / behaviour knowledge base

**Status: the Jungian core is built.** See [`knowledge/README.md`](../knowledge/README.md).

| Built | File |
|---|---|
| ✅ Jung's original model (attitudes, functions, auxiliary/inferior, compensation), from the public-domain 1923 text | `knowledge/01-jung-foundations.md` |
| ✅ The 8 cognitive functions, with how each sounds in a chat | `knowledge/02-cognitive-functions.md` |
| ✅ Stacks for all 16 types, the J/P rule, grip patterns, 3 development phases | `knowledge/03-type-dynamics.md` |
| ✅ Our own nicknames and group names | `knowledge/04-nicknames-and-groups.md` |
| ✅ Inference signals and the top-2 method | `knowledge/05-inference-signals.md` |
| ✅ 16 persona-oriented type profiles (voice, timing hints, conflict, stress, sample lines, classifier tells) | `knowledge/types/*.md` |

Reference sources: Jung's *Psychological Types* Ch. X (1923, public domain in the US, stored in `knowledge/sources/`) and A. J. Drenth's *The 16 Personality Types* (2013). Drenth's book is copyrighted, so we use its ideas as reference only and keep the PDF out of git. No content is taken from 16personalities.com.

We chose a curated, self-written knowledge base over downloading third-party skill packs. Those packs are unreviewed prompt text that would feed straight into persona behaviour.

Still to write (source material for persona realism):

| File | Content | Grounded in |
|---|---|---|
| `big-five-bridge.md` | MBTI ↔ Big Five correlations (McCrae & Costa 1989) | Personality research |
| `conversation-dynamics.md` | Turn-taking, backchannels ("mm", "wait really?"), repair, topic shifts | Conversation analysis (Sacks, Schegloff) |
| `politeness-and-face.md` | Face-work, politeness strategies, directness by type | Goffman; Brown & Levinson |
| `emotional-realism.md` | Mood carry-over, self-disclosure reciprocity, rapport building | Social penetration theory (Altman & Taylor) |
| `language-markers.md` | Deeper linguistic cues for traits (extends `05-inference-signals.md`) | Pennebaker (LIWC), Yarkoni 2010 |

Optionally, we can later wrap the persona-writing workflow as a project skill in `.claude/skills/` so that writing and tuning the 16 personas during development stays consistent.

---

## 10. Privacy, ethics, safety
- **Consent first:** typing-behaviour collection is opt-in, explained in plain words, and can be switched off.
- **Minimise data:** aggregate keystroke stats on the client. Never send or store raw keystrokes or deleted text.
- **Not a diagnosis:** the inference is labelled as an estimate, with confidence, and the user can disagree or reset it.
- **AI disclosure:** clear AI labelling in the product, plus the in-character honesty rule (section 5.2).
- **Wellbeing:** distress detection with real-help resources. Avoid designs that build unhealthy dependency (no guilt-tripping when the user leaves).
- **Age:** decide on a minimum age (13+ or 18+) before launch.

---

## 11. Build roadmap (each phase can be built separately)

| Phase | Deliverable | Done when |
|---|---|---|
| **0. Foundations** | Repo, TS setup, persona YAML schema, `knowledge/` drafts, 2 pilot personas (one I, one E; for example INFP and ESTJ) | Specs reviewed |
| **1. Conversation core** | Orchestrator, Persona Engine, structured replies, prompt caching, CLI harness | You can chat with both personas in a terminal and they feel distinct |
| **2. Human Behaviour Layer** | Delivery-plan generator and simulated playback in the CLI | Timing feels natural per type |
| **3. Inference** | Text analyser, style metrics, aggregator, snapshots, eval set | Per-axis accuracy measured on the eval |
| **4. Persistence and memory** | Postgres schema, memory extraction and recall | Replier remembers facts across sessions |
| **5. UI** (separate track) | Gallery, presence view, "your read" panel, telemetry collector | Matches design direction |
| **6. All 16 personas and polish** | Remaining 14 specs, persona evals, cost tuning | Each persona passes a "distinctness" eval |

---

## 12. Open questions for you
1. **Platform:** web only, or also mobile later? (This affects the telemetry collector.)
2. **Accounts:** anonymous sessions first, or login from day one?
3. **Inference visibility:** always visible, or revealed only after some conversation as a "reveal moment"?
4. **Persona identity:** fixed named characters (for example "Mira, INFP"), or a different human for the same type each time?
5. **Monetisation and cost:** is there a target cost per conversation? This decides model and effort tuning.
6. **Language:** English only, or multilingual? (The classifier's linguistic cues are language-specific.)
