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

Copy `.env.example` → `.env`.

| Key | Purpose |
| --- | --- |
| `GNANI_API_KEY` | Prisma STT + Timbre TTS |
| `GNANI_STT_LANGUAGE` | `indic-auto` (all regional languages) |
| `GROQ_API_KEY` | Groq key. Writes the spoken replies. Without it the built-in rule-based dialogue is used |
| `GROQ_MODEL` | Default `openai/gpt-oss-120b`. `openai/gpt-oss-20b` is faster and cheaper. Check Groq's deprecations page: models get retired |
| `UPSTASH_REDIS_REST_URL` | Upstash HTTPS endpoint |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash REST token |
| `MYSCHEME_API_KEY` | Live myScheme catalogue |

Without the Upstash **REST URL**, caching falls back to in-process memory (eager warm still runs).

## Languages (Gnani)

Hindi · English · Tamil · Telugu · Kannada · Malayalam · Marathi · Punjabi · Bengali · Gujarati  
STT: Prisma v3.0 `indic-auto` · TTS: Timbre v3.0 in the detected language

## Live desk

- WebSocket `/ws/live` streams 16 kHz PCM (1024-byte frames) to Prisma realtime
- Chat history persisted (Postgres + Redis mirror)
- Schemes from live myScheme, with search + prompt caching and eager warm of frequent queries

## How a live turn works

`understand` (profile from everything said, in any supported language) → `retrieve` (verified schemes only) →
`Groq` writes the reply from a strong system prompt plus trusted per-turn context → `guardrails` check it
(no invented schemes or amounts, no eligibility promises, right language, speakable) → Timbre speaks it.
If Evon is off, slow or fails a guardrail, the rule-based dialogue answers instead, so a turn never fails.
Messages are shown immediately and saved to the database in the background.
