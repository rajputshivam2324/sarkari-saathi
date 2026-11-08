# Sarkari Saathi — Backend

FastAPI backend for the voice-first Indian welfare-scheme finder. Speech-to-text uses **Gnani Prisma v3.0**; spoken replies use **Gnani Timbre v3.0** (voice Shivani, `hi-IN`). Optional **Evon** runs only when `GNANI_EVON_ENABLED=true` and `GNANI_EVON_URL` is set — never faked.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Environment is loaded from the project root `../.env` (see `.env.example`).

## Run

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API docs: http://localhost:8000/docs  
- Health: http://localhost:8000/health  

Tables are created on startup against `DATABASE_URL` (Neon Postgres).

## Auth

| Method | Path | Body |
|--------|------|------|
| POST | `/auth/register` | `{ "username", "password", "name?" }` |
| POST | `/auth/login` | `{ "username", "password" }` → JWT + user |
| GET | `/auth/me` | Bearer token |

## Voice

| Method | Path | Notes |
|--------|------|-------|
| POST | `/voice/turn` | Multipart: `audio` and/or `text`, optional `context` JSON. Returns transcript, follow-up, reply_text, schemes, models, `evon_ran`, `reply_audio_b64`. |
| POST | `/voice/speak` | JSON `{ "text" }` → WAV |

Send `Authorization: Bearer <token>`. Pass the previous turn’s `context` back on the next turn (up to 3 Hindi follow-ups, then top-3 scheme matches).

## Schemes

`GET /schemes` — curated catalogue (~18 central schemes with Hindi names and official URLs).
