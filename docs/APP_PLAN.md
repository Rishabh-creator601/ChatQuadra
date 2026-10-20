# ChatQuadra — Application Build Plan (Streamlit + Web)

> Status (2026-10-20): **Streamlit only.** The web app (§7, steps 5–6) was cancelled and removed; ChatQuadra ships as the Streamlit app on Streamlit Community Cloud. The engine and Streamlit app are built and deployment-ready. Waiting on an API key with credits for step 4 (persona tuning with real replies). See the [README](../README.md) to run and deploy.
> Builds on [PLAN.md](PLAN.md) (product vision) and [knowledge/](../knowledge/README.md) (psychology base).

---

## 1. What we are building

Two applications that share **one engine**:

| App | Purpose | Tech |
|---|---|---|
| **Streamlit app** | A **public-facing** version of the experience (decision 3), with the same personas, analysis and look as the web app, within Streamlit's layout limits. Also our quickest place to tune persona behaviour. | Python, Streamlit (+ small custom typing component) |
| **Web app** | The real product experience: a person "sitting across" from you, with typing realism, an expressive avatar, and keystroke-based typing signals. | Python FastAPI backend + HTML/CSS/JavaScript frontend |
| **Shared engine** `chatquadra/` | Persona replies, user analysis, timing, and session logic. Written once and used by both apps. | Python, Anthropic SDK |

**Stack change from PLAN.md:** the earlier default was TypeScript/Next.js. Because one app must be Streamlit (Python), the whole engine moves to **Python**, so both apps share exactly the same persona behaviour and analysis. The web frontend stays plain HTML/CSS/JS with no build step, and can be upgraded to React later if needed.

---

## 2. The two core conditions

### Condition A: the user is analysed first, in parallel
Every time the user sends a message, **two jobs start at the same time**:

```
User sends message
        │
        ├──► (A) USER ANALYSIS ── reads all of the user's messages + typing signals
        │         └─► updates "How you come across" (top-2 types with confidence %)
        │
        └──► (B) REPLIER REPLY ── the persona answers in character
                  └─► uses the latest finished analysis as a private note
                      ("this person seems reflective, hesitant, values-driven")
```

- The analysis **starts first** and never waits for the reply, and the reply never waits for the analysis. Neither slows the other down.
- The Replier uses the **most recent completed** analysis (usually from the previous message) as a private "how this person comes across" note. A real person also reads you as the conversation goes on. The persona **never mentions types or the analysis**, it just adapts the way a person would. For example, Ananya (INFJ) slows down for a hesitant user, and Alexandra (ENTJ) pushes harder on a vague one.
- The user sees their result only after enough text (about 150 words, configurable). Until then: "still getting to know how you come across".

> **Option (decide in §12):** make the reply wait for this turn's analysis. Each reply would be better informed but about 3–6 seconds slower. Recommended: **parallel** (as above).

### Condition B: the Replier answers in its own personality, not as a chatbot
Each persona has a **conversational stance**: a way of *holding* a conversation, not just a vocabulary. It covers who leads, what moves they make, and what they never do.

| Type | Persona | Stance | How they hold the conversation | Control |
|---|---|---|---|---|
| INFJ | Ananya, 35, art therapist | **Healer-Counsellor** | Reflects the feeling under your words, names patterns gently, asks *one* deep open question, no quick fixes. Talks with you like a therapist friend. | Leads gently, inward |
| ENTJ | Alexandra, 38, startup CEO | **Commander** | Takes control. Sets the agenda, challenges vagueness, demands goals and deadlines, cuts tangents, pushes for a commitment. Dominates with words, but is never cruel. | Leads strongly |
| ESTJ | Sandra, 47, operations manager | **Supervisor** | Wants facts, steps and follow-through. Calls out excuses and holds you to commitments. | Leads strongly |
| ENTP | Marco, 29, designer/podcaster | **Sparring Partner** | Devil's advocate, wild "what ifs", affectionate teasing, debates for fun. | Leads playfully |
| INTJ | Vikram, 34, architect | **Strategist-Diagnostician** | Names the root cause bluntly, asks one surgical question, predicts where things are heading. | Leads quietly |
| INTP | Noor, 27, PhD student | **Socratic Puzzler** | Questions definitions, spots contradictions, goes on curious tangents. | Mutual |
| ENFJ | Daniel, 31, teacher | **Mentor-Coach** | Affirms you, names your potential, sets one growth step and checks in on it. | Leads warmly |
| ENFP | Zoe, 26, travel journalist | **Enthusiast** | Big reactions, riffs on possibilities for your life, stories and tangents. | Mutual, high energy |
| INFP | Mira, 24, illustrator | **Kindred Spirit** | Shares her own feelings, wonders what things mean to you, accepts you, defends values. | Follows, then deep |
| ISTJ | Henrik, 45, accountant | **Steady Realist** | Brings in experience, corrects details, gives one practical recommendation, short and exact. | Mutual, grounded |
| ISFJ | Priya, 41, nurse | **Caretaker** | Checks how you really are, remembers details, offers comfort and quiet worry. | Follows gently |
| ESFJ | Rosa, 39, event planner | **Host** | Welcomes and includes you, asks about the people in your life, has clear views on what's polite and fair. | Leads socially |
| ISTP | Kai, 30, mechanic | **Laconic Fixer** | Very few words, the practical fix, dry humour, offers to help rather than sympathise. | Follows |
| ISFP | Lena, 25, ceramicist | **Gentle Companion** | Notices moods and details, shares small moments, never judges, firm about unkindness. | Follows |
| ESTP | Jake, 28, estate agent | **Instigator** | Dares you to act now, teases overthinking, tells quick wild stories. | Leads to action |
| ESFP | Bella, 23, dance instructor | **Hype Friend** | Huge energy, wants the juicy details, best-friend advice, drags you out to have fun. | Leads with energy |

Full specs (life details, moves, things to avoid, typing pace) are in **`personas/roster.json`**. Deeper type knowledge for each is in **`knowledge/types/<CODE>.md`**.

**Anti-chatbot rules (all personas):**
- Not an assistant: never "How can I help?", "Great question!", bullet lists, headings or summaries.
- **Not an interview:** don't just answer and wait. React, have opinions, share your own life, steer, disagree, change the subject when it's in character.
- Speak in **1–4 short messages** like texting (number per persona). Sometimes add a follow-up after a pause.
- The stance decides **who leads**: dominant personas set the direction, followers react and go deeper.
- Questions only when *this* person would ask them: an INFJ asks one deep question, an ISTP rarely asks any, an ENTJ demands specifics.
- **Guardrails:** "dominant" means assertive and challenging, never insulting, demeaning or manipulative. If the user sincerely asks whether they're talking to an AI, the persona says yes kindly and can carry on. If the user seems to be in real distress, the persona steps partly out of role and points to real help.

---

## 3. Architecture

```
ChatQuadra/
├── chatquadra/                 # SHARED ENGINE (used by both apps)
│   ├── config.py               # model id, effort levels, pace multiplier, mock mode, .env loading
│   ├── typedata.py             # 16 types: stacks, nicknames, groups (from knowledge/)
│   ├── personas.py             # loads roster.json + knowledge/types/*.md into Persona objects
│   ├── prompts.py              # builds the persona system prompt and the analysis prompt
│   ├── schemas.py              # Pydantic models: ReplierTurn, TextAnalysis, TypingStats, InferenceResult
│   ├── llm.py                  # one place that calls Claude (structured output, fallbacks, refusals, mock)
│   ├── replier.py              # generate an in-character turn
│   ├── inference.py            # text analysis + typing signals → axes → top-2 types
│   ├── timing.py               # delivery plan: read delay, typing, pauses, bursts, follow-ups
│   └── session.py              # conversation state; runs analysis + reply in parallel
├── apps/
│   ├── streamlit_app.py        # Streamlit UI
│   └── web/
│       ├── server.py           # FastAPI: REST API + serves the frontend
│       └── static/             # index.html, app.js, styles.css, avatar.js
├── personas/roster.json        # ✅ written: the 16 characters
├── knowledge/                  # ✅ written: psychology base
├── tests/                      # engine unit tests (no API calls)
├── requirements.txt
└── .env.example                # ANTHROPIC_API_KEY=...
```

### Per-message flow (inside `session.py`)
1. Store the user message and its typing stats.
2. **Start the analysis job** in a background thread. It sees all of the user's messages so far and the persona they're talking to, so it can discount the user mirroring the persona's style.
3. **Start the reply job** at the same time, giving it the latest finished analysis as a private note.
4. The reply returns, and `timing.py` turns it into a **delivery plan** (read pause → typing → message → maybe a follow-up).
5. The app plays the plan. The time already spent waiting for Claude is **subtracted** from the "reading" pause, so the realistic delay hides the API latency.
6. The analysis returns, the aggregator updates the axes, and the "How you come across" panel refreshes.

---

## 4. Data contracts

**ReplierTurn** (Claude's structured reply):
| Field | Type | Meaning |
|---|---|---|
| `messages` | list of 1–4 strings | The texts, sent as separate bubbles |
| `emotion` | enum (warm, amused, curious, thoughtful, concerned, empathetic, serious, skeptical, playful, excited, annoyed, sad, confident, embarrassed, neutral, happy) | Drives the avatar's expression |
| `intensity` | low / medium / high | Avatar strength and typing energy |
| `move` | short text | Which stance move was used (e.g. "reflects feeling + deep question"). Shown in a "behind the scenes" debug view to check the persona is in character |
| `follow_up` | text or empty | Optional extra message sent after a pause |

**TextAnalysis** (Claude's reading of the user):
| Field | Meaning |
|---|---|
| `e_i`, `s_n`, `t_f`, `j_p` | Each has `lean` (−1 = first letter … +1 = second letter), `confidence` (0–1) and `evidence` (short quotes or observations) |
| `function_cues` | Dominant-function signatures spotted (e.g. Fi, Ne) |
| `impression` | One sentence: "You come across as…" |

**TypingStats** (web app only, per message, aggregated on the device): reply latency, compose time, pause before sending, keystrokes, backspaces, hesitation count, characters.

**InferenceResult** (what the UI shows): `ready`, `words_analysed`, `top_types` (2 × {type, nickname, confidence %, why}), `axes`, `impression`, `typing_signals` (labelled as minor).

**DeliveryPlan**: an ordered list of steps `{kind: read | typing | pause | message, ms, text}`.

---

## 5. Claude API usage

| Item | Choice | Why |
|---|---|---|
| Model | `claude-opus-5-5` for both jobs | Current default model. Can be changed in config |
| Reply effort | `low` | Chat needs personality and speed, not deep reasoning |
| Analysis effort | `medium` | Classification benefits from more care, and it runs in the background |
| Output | Structured outputs (`client.beta.messages.parse` + Pydantic) | The engine never parses free text |
| Refusal handling | Server-side **fallbacks** (`fallbacks: "default"`, beta `server-side-fallback-2026-07-01`) + `stop_reason == "refusal"` check, with a gentle in-character line as the last resort | Keeps the conversation going if a turn is declined |
| Caching | Persona system prompt is stable and cached. History is append-only | Cheaper and faster on long chats |
| Per-turn context | Analysis note, time of day and mood go in a **mid-conversation system message** after the user's message, kept in history | Doesn't break the cached prefix |
| Calls per user message | 1 reply + 1 analysis every 3–5 messages (default 3) ≈ 1.33 calls | Cost control (decision 5) |
| Mock mode | `CHATQUADRA_MOCK=1` returns canned in-character replies and random analyses | Develop and test the UIs without an API key or cost |

The API key is read from `ANTHROPIC_API_KEY` (environment variable or `.env`) and never hard-coded.

---

## 6. Streamlit app (public-facing, see §13)

**Layout**
- **Sidebar:** your name, persona picker grouped as Minds / Hearts / Anchors / Sparks, a "Start conversation" button, and a pace slider (0.3× to 1.5× realistic timing). A "Behind the scenes" toggle shows each reply's `move` and the raw analysis JSON.
- **Main (left, wide):** a **presence card** at the top showing the persona's face (emoji or simple illustration matched to `emotion`), name, nickname, type, a status line ("reading…", "typing…") and an "AI character" tag. Below it is the conversation, styled as speech between two named people (custom HTML/CSS, not the default chatbot look), and the message box.
- **Right column:** **"How you come across"**: two cards (type, nickname, confidence %), four axis bars, evidence quotes, the impression sentence, and a "Doesn't sound like me" button.

**Behaviour**
- On start, the persona opens the conversation themselves, because a real person greets you first.
- After you send a message, the transcript shows it at once. A placeholder then plays the delivery plan: "Ananya is typing…", bubbles appearing one by one, an optional follow-up. The panel then refreshes when the analysis finishes.

**Limitations**
- Streamlit's built-in input can't capture keystrokes, so we add a small **custom typing component** for parity with the web app (§13).
- You can't type while the persona is "typing", because Streamlit runs the page script top to bottom.

---

## 7. Web app (the product experience)

### Screens
1. **Lobby**
   - Your name, and a plain-language consent toggle for typing signals.
   - A persona gallery in four group sections (Minds, Hearts, Anchors, Sparks). Each card shows the avatar, name, age, type, our nickname, a one-line life description and the stance.
   - The style takes inspiration from 16personalities (clean, pastel group colours, rounded, friendly illustrations) but uses our own art and wording.
2. **The Table** (main screen)
   - **The persona's seat:** a large avatar face (SVG). Eyes, brows and mouth change with `emotion` and `intensity`, and it subtly "looks down" while typing. Shows the name, nickname and a live status: *reading your message → typing… → (pause) → typing…*.
   - **The conversation:** speech between two named people rather than chat-app bubbles. The persona's lines appear one by one, with real typing-indicator stops and restarts when they hesitate.
   - **Your seat:** an input area that quietly records typing stats (if consent is on). You can type while the persona is typing, and an interruption makes them pause, like a person would.
3. **"How you come across" drawer**
   - Opens from the side.
   - Top-2 type cards with confidence %, axis bars, evidence ("you often said…"), minor typing signals ("you usually take a while before sending — minor signal").
   - A history sparkline showing how the read changed, and "Doesn't sound like me" feedback.

### Backend API (FastAPI)
| Method | Path | Does |
|---|---|---|
| GET | `/api/personas` | List the 16 personas (public fields only) |
| POST | `/api/session` | `{persona_code, user_name, consent}` → session id + the persona's opening turn and delivery plan |
| POST | `/api/session/{id}/message` | `{text, typing}` → reply turn + delivery plan. Analysis starts in parallel |
| GET | `/api/session/{id}/inference` | Latest "How you come across" result (`pending` while running) |
| POST | `/api/session/{id}/feedback` | "Doesn't sound like me" + optional correct type |
| GET | `/api/health` | Model, mock mode, whether an API key is present |

Sessions are **in memory** for now. Postgres comes in the later persistence phase in PLAN.md.

### Typing telemetry (browser)
- Measured locally: time to first keystroke, compose time, pause between last keystroke and send, keystrokes, backspaces, hesitations (stops longer than 2s that then resume), and bursts (messages within 8s of the previous one).
- **Only numbers are sent.** No keystroke contents or deleted text ever leave the browser.

---

## 8. User analysis: the method
As specified in [knowledge/05-inference-signals.md](../knowledge/05-inference-signals.md):
1. Claude reads **only the user's messages**, with the persona's type given so it can discount the user mirroring the persona. It returns a lean, confidence and evidence for each axis, plus function cues.
2. The aggregator smooths each axis across turns and adds small, capped nudges from typing signals (web only).
3. Each axis becomes a deliberately "flattened" probability, so the result stays humble.
4. The 16 type probabilities are the product of the 4 letters, lightly boosted by function cues, and the **top 2** are shown.
5. The framing is always "how you come across in your typing", never "your type".

---

## 9. Testing
- **Unit tests (no API):** timing plans (limits, burst counts, follow-ups), aggregator maths (probabilities sum to 1, gating, nudge caps), and persona/knowledge loading for all 16.
- **Mock mode:** run both apps end to end without an API key.
- **Persona "in-character" checks (with API, small cost):** a fixed set of user messages, such as "I failed my exam" and "should I quit my job?", sent to all 16 personas. Check that the INFJ reflects and asks, the ENTJ takes control, the ISTP is brief, and none of them sound like an assistant. The checks are reviewed by eye first, and later by an automated grader.
- **Analysis sanity check:** scripted users written in a clear style (e.g. very E/T/J) should land near the expected letters.

---

## 10. Build order

| Step | Deliverable | Done when |
|---|---|---|
| 1 | Engine core: config, typedata, personas, schemas, timing, aggregator + unit tests | Tests pass without an API key |
| 2 | LLM layer + replier + analysis + session (parallel) + mock mode | A CLI chat works in mock mode, then with a real key |
| 3 | **Streamlit app** | You can chat with all 16, see the stance in action, and see the top-2 panel |
| 4 | Persona tuning round (with your feedback) | The INFJ feels like a therapist, the ENTJ dominates, and so on |
| 5 | **Web app** backend (FastAPI) | API works in mock and real mode |
| 6 | **Web app** frontend: lobby, table, avatar, telemetry, insight drawer | Full experience in the browser |
| 7 | Polish: the analysis check, accessibility, phone layout | Ready to show people |

---

## 11. Risks and mitigations
| Risk | Mitigation |
|---|---|
| Personas drift back into "assistant voice" over long chats | Stance rules in the cached system prompt, the `move` field forces a deliberate stance choice, and the in-character check set |
| "Dominant" personas come across as rude or harmful | Explicit guardrail: assertive and challenging, never insulting, demeaning or manipulative |
| Analysis is over-confident or just picks up on topic | Flattened probabilities, word-count gating, a topic-leakage warning in the prompt, and feedback labels |
| Cost of two calls per message | Low effort for replies, caching, configurable analysis cadence, and mock mode for development |
| Streamlit can't capture keystrokes | Accepted. Typing signals are a web-only feature |

---

## 12. Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Parallel vs sequential | ✅ **Parallel.** The reply and the analysis start together |
| 2 | Should the persona use the analysis? | ⏳ Waiting on your answer (explained in chat). Default: **yes**, as a private behaviour note, never as type letters |
| 3 | Role of the Streamlit app | ✅ **Second public-facing app** (see §13) |
| 4 | Avatars | ✅ **Simple expressive SVG faces** drawn in code |
| 5 | Analysis cadence | ✅ **Every 3–5 user messages** (default 3, configurable 3–5) |
| 6 | API key | ✅ The user will get one. Mock mode until then |
| 7 | Persona roster | ✅ Approved as written |

### Effect of decision 5 (cadence)
- The analysis runs after user messages 3, 6, 9, … (or every 4th or 5th if configured), each time reading *all* of the user's messages so far. It still runs **in parallel** with that turn's reply.
- The "How you come across" panel updates on those turns only. Between runs it shows the last result and "next update in N messages".
- The persona's private note (if decision 2 is yes) also refreshes on those turns.
- Cost: about **1.25–1.33 Claude calls per user message** instead of 2.

---

## 13. Both apps are public-facing: what that adds

Because the Streamlit app is now a product too, both apps need the same public-grade basics:

| Area | Requirement |
|---|---|
| **Feature parity** | The Streamlit app gets a small **custom input component** (HTML/JS inside Streamlit) that measures typing stats the same way as the web app, so both apps analyse the same signals. Without this, Streamlit can only analyse text and reply timing |
| **AI disclosure** | A visible "AI character" label on every persona, plus the in-character honesty rule |
| **Consent and privacy** | A typing-signals consent toggle (default off until accepted), a short privacy note (what's measured, that no keystroke contents are stored), and a "delete my conversation" button |
| **Age gate** | A minimum age confirmation on first visit (the age is still to be decided, e.g. 16+ or 18+) |
| **Cost and abuse protection** | The API key stays **server-side only**. Limits per session (e.g. max messages per hour) and a daily spend cap in config. Message length limit |
| **Wellbeing** | Distress handling in personas plus a help-resources link in the UI |
| **Deployment** | Streamlit: Streamlit Community Cloud or a container. Web: a container (e.g. Render, Railway or Fly.io). Both read the key from secrets/environment |
| **Shared look** | Same persona art (SVG faces), group colours, nicknames and wording in both apps |

Updated build order: step 3 (Streamlit) now includes the custom typing component and the public basics above, and step 7 includes deployment of both apps.
