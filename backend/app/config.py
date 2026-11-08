from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

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

    # Conversation LLM: Groq (OpenAI-compatible). Gnani is used for speech only (STT + TTS).
    # Without GROQ_API_KEY the app still works on the built-in rule-based dialogue.
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
