"""
Shared config for the speech package (§4 ASR + TTS).

Own config module rather than importing §2's -- ASR/TTS config (model size,
device, compute type, voice) is a disjoint concern from LLM provider config;
the only thing worth sharing is the same __file__-based path-resolution +
load_dotenv pattern §2's config.py already established, which is cheap to
just repeat here.

Named `speech_config.py`, not `config.py` -- both this directory and §2's
have their own config module; §5's UI imports from both in one process, and
a bare `import config` from each would silently collide (the second import
just returns whichever module Python already cached under that name, not
the intended one) -- a real bug caught by testing that combined import
before writing the UI, not a hypothetical worry.
"""

import os

from dotenv import load_dotenv

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(MODULE_DIR))

load_dotenv(os.path.join(REPO_ROOT, ".env"))

# --- ASR (§4.1) ---
# Decided: faster-whisper, local/free, no API key or billing -- same
# cost-conscious reasoning as §1.3's local sentence-transformers embeddings,
# confirmed with the user before adding as a new dependency.
ASR_PROVIDER = os.environ.get("ASR_PROVIDER", "faster-whisper")
ASR_MODEL_SIZE = os.environ.get("ASR_MODEL_SIZE", "base")
ASR_DEVICE = os.environ.get("ASR_DEVICE", "cpu")
ASR_COMPUTE_TYPE = os.environ.get("ASR_COMPUTE_TYPE", "int8")

# --- TTS (§4.2) ---
# Decided: OpenAI TTS -- paid but cheap (~$15/1M chars; a ~40-word/~15s
# answer is a small fraction of a cent), reuses OPENAI_API_KEY, confirmed
# with the user before adding as the §4.2 provider over free local (pyttsx3
# -- quality judged too big a hit for a voice-assistant demo) and ElevenLabs
# (would need a brand-new service/key).
TTS_PROVIDER = os.environ.get("TTS_PROVIDER", "openai")
TTS_MODEL = os.environ.get("TTS_MODEL", "tts-1")
TTS_VOICE = os.environ.get("TTS_VOICE", "alloy")
TTS_MAX_SECONDS = 15.0  # matches the Answerer's (§2.5) spoken-summary length budget

if TTS_PROVIDER == "openai":
    _has_key = bool(os.environ.get("OPENAI_API_KEY"))  # presence only -- never read/printed
    assert _has_key, (
        "OPENAI_API_KEY missing -- copy .env.example to .env and fill it in "
        "(needed for TTS_PROVIDER=openai)"
    )
