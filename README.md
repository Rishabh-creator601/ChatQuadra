# ChatQuadra

Sit across from one of sixteen characters, each with their own personality and way of holding a conversation, and see how *you* come across in the way you type. A Streamlit app.

- **Characters, not chatbots.** Each persona has a conversational stance. Ananya (INFJ) reflects feelings and asks one deep question like a therapist friend. Alexandra (ENTJ) takes control and pushes you to decide. Kai (ISTP) barely says a word. See `personas/roster.json`.
- **You're read in parallel.** If you don't know your type, every 3 messages an analysis of your typing runs alongside the reply and shows your two most likely types with confidence. It's an estimate, not a diagnosis. If you know your type, you can just say so and nothing is analysed.
- **Bring your own key.** Each visitor uses their own Anthropic or OpenAI API key, so the host pays nothing for conversations.

Docs: [product plan](docs/PLAN.md), [app build plan](docs/APP_PLAN.md), [psychology knowledge base](knowledge/README.md), [Reddit community data](community/reddit/README.md).

## Run locally

```bash
pip install -r requirements.txt
streamlit run apps/streamlit_app.py        # → http://localhost:8501
```

On the first page, each visitor gives their name, says whether they know their MBTI, chooses a platform (**Anthropic** or **OpenAI**, OpenAI preselected) and enters their own API key. The app stays locked until the key passes a one-request check (valid, can use a supported model, has credits). Keys are kept only in that browser session's memory and never saved. For OpenAI, the first available of `gpt-5.1`, `gpt-5`, `gpt-4.1`, `gpt-4o` is used (override with `CHATQUADRA_OPENAI_MODEL`).

**Developer demo mode:** `CHATQUADRA_MOCK=1 streamlit run apps/streamlit_app.py` skips the key and uses canned lines plus the writing-style reading. Useful for UI work at no cost.

## Deploy to Streamlit Community Cloud

1. **Put the project on GitHub.** From the project folder:
   ```bash
   git init
   git add .
   git commit -m "ChatQuadra"
   git branch -M main
   git remote add origin https://github.com/<you>/chatquadra.git
   git push -u origin main
   ```
   `.gitignore` already keeps out `.env` (your key), the raw Reddit downloads, the copyrighted PDF and caches. Run `git status` before committing to be sure.
2. **Create the app** at [share.streamlit.io](https://share.streamlit.io): *Create app* → *Deploy a public app from GitHub* →
   - Repository: `<you>/chatquadra`, branch `main`
   - Main file path: **`apps/streamlit_app.py`**
   - *Advanced settings* → Python version **3.11** (3.10+ works)
3. **Secrets: none needed.** Visitors bring their own API keys. Do **not** set `CHATQUADRA_MOCK` in production.
4. Click **Deploy**. Streamlit Cloud installs `requirements.txt` and applies `.streamlit/config.toml` (theme, hidden tracebacks, no usage stats) automatically.

Optional settings, added in the app's *Settings → Secrets* (or as environment variables):

| Setting | Default | What it does |
|---|---|---|
| `CHATQUADRA_MODEL` | `claude-opus-5-5` | Anthropic model |
| `CHATQUADRA_OPENAI_MODEL` | first available from the list above | OpenAI model |
| `CHATQUADRA_ANALYSIS_EVERY` | `3` | Read the user every 3–5 messages |
| `CHATQUADRA_MIN_WORDS` | `150` | Words before a reading is shown |
| `CHATQUADRA_MAX_MESSAGES_PER_HOUR` | `120` | Per-conversation message limit |

## Test

```bash
pip install -r requirements-dev.txt
CHATQUADRA_MOCK=1 python -m pytest -q tests     # no API calls
```

GitHub Actions runs the same tests on every push (`.github/workflows/tests.yml`).

## Layout

```
apps/            streamlit_app.py (pages 1-3), streamlit_pages.py (Summary/About/References),
                 streamlit_views.py (HTML/CSS), streamlit_typing/ (typing-rhythm input component)
chatquadra/      engine: personas, prompts, model calls (Anthropic/OpenAI), analysis, timing, sessions, avatars
chatquadra/data/ style_model.json, the trained writing-style model
personas/        roster.json: the 16 characters and their conversational stances
knowledge/       Jungian type theory and 16 type profiles the personas are built from
community/reddit/ community profiles and statistics from Reddit (raw downloads stay local)
tests/           engine tests
```

## Notes
- API keys stay on the server, in the visitor's session only. They're never written to disk or logs.
- Typing signals are opt-in and only numbers (timing, edits) are used, never keystroke contents.
- Personas tell users they're AI if sincerely asked, and point to real help if someone seems to be in crisis.
