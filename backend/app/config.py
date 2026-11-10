from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"   # backend/.env: the frontend has its own, in frontend/.env

# Gnani Prisma / Timbre — all supported regional languages
GNANI_LANGUAGES = [
    "hi-IN",  # Hindi
    "en-IN",  # English
    "ta-IN",  # Tamil
    "te-IN",  # Telugu
    "kn-IN",  # Kannada
    "ml-IN",  # Malayalam
    "mr-IN",  # Marathi
    "pa-IN",  # Punjabi
    "bn-IN",  # Bengali
    "gu-IN",  # Gujarati
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Sarkari Saathi"
    environment: str = "development"
    database_url: str
    secret_key: str
    frontend_origin: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    jwt_expire_hours: int = 72

    gnani_api_key: str = ""
    gnani_evon_enabled: bool = False
    gnani_evon_url: str = ""

    gnani_stt_url: str = "https://api.vachana.ai/stt/v3"
    gnani_stt_ws_url: str = "wss://api.vachana.ai/stt/v3/stream"
    gnani_tts_url: str = "https://api.vachana.ai/api/v1/tts/inference"
    gnani_tts_ws_url: str = "wss://api.vachana.ai/api/v1/tts"
    gnani_stt_model: str = "prisma-v3.0"
    gnani_tts_model: str = "timbre-v3.0"
    gnani_tts_voice: str = "Shivani"
    # indic-auto covers every regional language on the key (Prisma max list is 4)
    gnani_stt_language: str = "indic-auto"
    gnani_tts_language: str = "hi-IN"

    # Conversation LLM (OpenAI-compatible chat completions). Gnani is used for speech only (STT + TTS).
    # Gemini is used when GEMINI_API_KEY is set, otherwise Groq when GROQ_API_KEY is set. With neither key the app
    # still works on the built-in rule-based dialogue.
    gemini_api_key: str = ""
    # Extra Gemini keys (ideally from separate Google projects: quota is counted per project). Requests are
    # spread across all of them and a key that hits its limit is rested while the others carry on.
    gemini_api_key2: str = ""
    gemini_api_key3: str = ""
    gemini_api_key4: str = ""
    gemini_api_key5: str = ""
    gemini_api_key6: str = ""
    gemini_api_key7: str = ""
    gemini_api_key8: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Used for a key whose account can no longer call gemini_model ("no longer available to new users").
    gemini_fallback_model: str = "gemini-3.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    # "none" switches Gemini's thinking off: fastest, and thinking tokens can no longer eat the reply budget.
    gemini_reasoning_effort: str = "none"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_reasoning_effort: str = "low"  # gpt-oss / qwen only: keeps voice replies fast
    llm_timeout_s: float = 12.0
    llm_max_tokens: int = 600  # reasoning models spend part of this on thinking
    llm_temperature: float = 0.5

    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    upstash_redis_url: str = ""  # optional rediss:// TCP URL

    myscheme_api_key: str = ""  # set MYSCHEME_API_KEY in .env (see .env.example)
    myscheme_api_base: str = "https://api.myscheme.gov.in"

    @property
    def gemini_keys(self) -> list[str]:
        """Every configured Gemini key, in order, without blanks or duplicates."""
        raw = [
            self.gemini_api_key, self.gemini_api_key2, self.gemini_api_key3, self.gemini_api_key4,
            self.gemini_api_key5, self.gemini_api_key6, self.gemini_api_key7, self.gemini_api_key8,
        ]
        return list(dict.fromkeys(k.strip() for k in raw if k and k.strip()))


@lru_cache
def get_settings() -> Settings:
    return Settings()
