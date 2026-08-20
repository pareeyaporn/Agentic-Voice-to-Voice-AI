"""
TTS module (§4.2). Text-to-speech via OpenAI's TTS API -- cheap (~$15/1M
chars), reuses OPENAI_API_KEY. Provider-swappable by construction
(TTS_PROVIDER in speech_config.py); only the openai path is implemented.

Fragment-based: generates the full clip, then returns it for the UI to
play (no streaming). The <=15s budget is enforced by measuring actual
audio duration after synthesis, not by trusting the Answerer's ~40-word
proxy -- if over budget, the clip is regenerated once at a faster `speed`.

Text-only fallback on a synthesis failure is a UI-layer decision; this
module's job is only to fail loud and typed (TTSError).
"""

import io
import wave
from dataclasses import dataclass

from speech_config import TTS_MAX_SECONDS, TTS_MODEL, TTS_PROVIDER, TTS_VOICE, require_tts_config

_client = None  # lazy singleton, same reasoning as asr.py's _model


class TTSError(Exception):
    """Typed so the UI can catch this specifically for its text-only
    fallback, rather than a bare Exception."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    format: str  # "wav"
    duration_seconds: float
    speed_used: float


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        # §4.3: bounded timeout -- the SDK's own default is 600s, which would
        # leave the UI's spinner running for up to 10 minutes on a hung call.
        _client = OpenAI(timeout=30.0, max_retries=1)
    return _client


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    """Computed from the actual received byte count, not wave.getnframes():
    OpenAI's streamed 'wav' response sets the RIFF/data chunk sizes to the
    placeholder 0xFFFFFFFF (length unknown at encode time), which the
    stdlib wave module takes at face value -- turning a real ~2s clip into
    a reported ~24.8 DAY duration. The 'fmt ' subchunk is unaffected, so
    channel/width/rate are read normally; only the payload length is
    computed manually from the actual buffer."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
    data_offset = wav_bytes.find(b"data")
    if data_offset == -1:
        raise TTSError("Malformed WAV response: no 'data' chunk found")
    payload_bytes = len(wav_bytes) - (data_offset + 8)
    frame_size = nchannels * sampwidth
    return payload_bytes / float(frame_size * framerate)


def _synthesize_once(text: str, speed: float) -> bytes:
    client = _get_client()
    response = client.audio.speech.create(
        model=TTS_MODEL, voice=TTS_VOICE, input=text, response_format="wav", speed=speed
    )
    return response.read()


def synthesize(text: str, max_seconds: float = TTS_MAX_SECONDS) -> SynthesisResult:
    """Returns the full synthesized clip as WAV bytes -- fragment-based, no
    streaming. Raises TTSError on any failure (bad provider config, empty
    text, API error, network) so the caller gets a typed exception instead
    of an uncaught one."""
    if TTS_PROVIDER != "openai":
        raise TTSError(
            f"TTS_PROVIDER={TTS_PROVIDER!r} has no implemented synthesis path (only 'openai' is built)"
        )
    if not text or not text.strip():
        raise TTSError("Cannot synthesize empty text")
    try:
        require_tts_config()
    except RuntimeError as e:
        raise TTSError(str(e)) from e

    try:
        audio_bytes = _synthesize_once(text, speed=1.0)
        duration = _wav_duration_seconds(audio_bytes)
        speed_used = 1.0

        if duration > max_seconds:
            # Regenerate once at a proportionally faster speed rather than
            # ship an over-budget clip. Capped to OpenAI's speed range (0.25-4.0).
            needed_speed = min(4.0, max(0.25, speed_used * (duration / max_seconds)))
            audio_bytes = _synthesize_once(text, speed=needed_speed)
            duration = _wav_duration_seconds(audio_bytes)
            speed_used = needed_speed

        return SynthesisResult(
            audio_bytes=audio_bytes, format="wav", duration_seconds=duration, speed_used=speed_used
        )
    except TTSError:
        raise
    except Exception as e:
        # openai SDK can raise several distinct error types -- normalized to one TTSError
        raise TTSError(f"Speech synthesis failed: {e}") from e
