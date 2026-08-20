"""
Shared config for the speech package (§4 ASR + TTS).

Own config module rather than importing §2's -- ASR/TTS config is a
disjoint concern from LLM provider config, and §5's UI imports both in one
process. Named `speech_config.py`, not `config.py`: two same-named bare
`config` modules would silently collide (the second import just reuses the
first's cached module) -- confirmed by testing that combined import.
"""

import os

from dotenv import load_dotenv

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

load_dotenv(os.path.join(REPO_ROOT, ".env"))

# --- ASR (§4.1): local faster-whisper, free, no API key ---
ASR_PROVIDER = os.environ.get("ASR_PROVIDER", "faster-whisper")
ASR_MODEL_SIZE = os.environ.get("ASR_MODEL_SIZE", "base")
ASR_DEVICE = os.environ.get("ASR_DEVICE", "cpu")
ASR_COMPUTE_TYPE = os.environ.get("ASR_COMPUTE_TYPE", "int8")

# --- TTS (§4.2): OpenAI TTS -- cheap (~$15/1M chars), reuses OPENAI_API_KEY ---
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "openai")
TTS_MODEL = os.environ.get("TTS_MODEL", "tts-1")
TTS_VOICE = os.environ.get("TTS_VOICE", "alloy")
TTS_MAX_SECONDS = 15.0  # matches the Answerer's (§2.5) spoken-summary length budget

def require_tts_config() -> None:
    """Validates TTS env vars at first synthesis, not at import -- app.py
    imports this module unconditionally, and mock-data mode (§5.1, which
    never synthesizes) must work with no .env at all."""
    if TTS_PROVIDER == "openai":
        _has_key = bool(os.environ.get("OPENAI_API_KEY"))  # presence only -- never read/printed
        if not _has_key:
            raise RuntimeError(
                "OPENAI_API_KEY missing -- copy .env.example to .env and fill it in "
                "(needed for TTS_PROVIDER=openai)"
            )
