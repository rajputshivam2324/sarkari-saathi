# Sarkari Saathi · बोलिए, योजना पाइए

Live voice finder for Indian welfare schemes. Speak any Gnani-supported language; get matched योजना from **myScheme.gov.in** with official links, spoken back via Timbre.

## Run

```bash
# Backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

Open http://127.0.0.1:5173 → register → **Start speaking** → tap the mic for **live** talk.

## Env

The backend and the frontend each have their own env file. Neither is committed.

| File | Template | Holds |
| --- | --- | --- |
| `backend/.env` | `backend/.env.example` | Database, Gnani, Gemini/Groq, Redis, myScheme, JWT secret. **Secrets.** |
| `frontend/.env` | `frontend/.env.example` | `VITE_API_URL`, `VITE_WS_URL`. Public values compiled into the JavaScript: no secrets. |

```bash
cp backend/.env.example backend/.env     # then fill it in
cp frontend/.env.example frontend/.env   # the defaults work for local development
```

Backend keys (full list and comments in `backend/.env.example`):

| Key | Purpose |
| --- | --- |
| `GNANI_API_KEY` | Prisma STT + Timbre TTS |
| `GNANI_STT_LANGUAGE` | `indic-auto` (all regional languages) |
| `GEMINI_API_KEY` … `GEMINI_API_KEY8` | Google AI Studio keys. Write the spoken replies through Gemini's OpenAI-compatible endpoint (no SDK). Use keys from **separate Google projects**: quota is counted per project, and requests are spread across the keys. A key that hits its limit rests while the others carry on |
| `GEMINI_MODEL` | Default `gemini-2.5-flash` |
| `GEMINI_FALLBACK_MODEL` | Default `gemini-3.5-flash`. Used for keys whose account can no longer call `GEMINI_MODEL` |
| `GEMINI_REASONING_EFFORT` | `none` (default, fastest), `low`, `medium` or `high` |
| `GROQ_API_KEY` | Optional spare. Used only when every Gemini key is resting or none is set. With no LLM key the built-in rule-based dialogue is used |
| `GROQ_MODEL` | Default `openai/gpt-oss-120b` |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | Upstash HTTPS endpoint and token |
| `MYSCHEME_API_KEY` | Live myScheme catalogue |

Without the Upstash **REST URL**, caching falls back to in-process memory (eager warm still runs).

## Deploy

Backend on Google Cloud Run, with a subdomain of `shivamio.in`: see [docs/DEPLOY_GCP.md](docs/DEPLOY_GCP.md).

## Languages (Gnani)

Hindi · English · Tamil · Telugu · Kannada · Malayalam · Marathi · Punjabi · Bengali · Gujarati  
STT: Prisma v3.0 `indic-auto` · TTS: Timbre v3.0 in the detected language

## Live desk

- WebSocket `/ws/live` streams 16 kHz PCM (1024-byte frames) to Prisma realtime
- Chat history persisted (Postgres + Redis mirror)
- Schemes from live myScheme, with search + prompt caching and eager warm of frequent queries

## How a live turn works

`understand` (profile from everything said, in any supported language) → `retrieve` (verified schemes only) →
`LLM` (Gemini 2.5 Flash, or Groq) writes the reply from a strong system prompt plus trusted per-turn context → `guardrails` check it
(no invented schemes or amounts, no eligibility promises, right language, speakable) → Timbre speaks it.
If Evon is off, slow or fails a guardrail, the rule-based dialogue answers instead, so a turn never fails.
Messages are shown immediately and saved to the database in the background.
