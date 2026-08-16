"""
TTS module (§4.2). Text-to-speech via OpenAI's TTS API -- paid but cheap
(~$15/1M chars; a ~40-word/~15s answer is a small fraction of a cent),
reuses OPENAI_API_KEY already in .env, confirmed with the user before
adding as the §4.2 provider (weighed against a free local option -- a
pyttsx3 branch was judged too rough a quality hit for a voice-assistant
demo -- and ElevenLabs, which would've needed a brand-new service/key).

Provider-swappable by construction (TTS_PROVIDER in config.py), same pattern
as §2.6's get_chat_model(): only the openai path is actually implemented and
exercised; a future local/ElevenLabs/Azure/Polly branch would slot in the
same way, stated as not attempted rather than silently unsupported.

.py per the file-format convention (reason (c): the UI (§5, not yet built)
imports synthesize() directly per query).

Fragment-based only: generates the full audio clip, then returns it for the
UI to play. Streaming synthesis is the backlog's own stated stretch goal.

The <=15s length budget is enforced here, deterministically, not just
inherited from the Answerer's ~40-word budget: word count is a proxy for
speech duration, not the duration itself (speaking rate varies by content
and voice), so actual audio duration is measured after synthesis and, if
it's over budget, the clip is regenerated once at a proportionally faster
`speed` -- same "don't trust the proxy, verify the real thing" posture as
§2.5's scrub_raw_ids()/enforce_length().

Handling a synthesis failure with a text-only fallback (§4.2/§5.3's own
requirement) is a UI-layer decision -- this module's job is only to fail
loud and typed (TTSError) so the UI has something to catch, not to decide
what the UI does about it.
"""

import io
import wave
from dataclasses import dataclass

from config import TTS_MAX_SECONDS, TTS_MODEL, TTS_PROVIDER, TTS_VOICE

_client = None  # lazy singleton, same reasoning as asr.py's _model


class TTSError(Exception):
    """Typed so the UI (§4.2/§5.3: 'TTS failure' -> text-only fallback) can
    catch this specifically rather than a bare Exception -- same posture as
    §3.4's ToolError and asr.py's ASRError."""

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

        _client = OpenAI()
    return _client


def _wav_duration_seconds(wav_bytes: bytes) -> float:
    """Computed from the actual received byte count, not wave.getnframes().
    Real bug found by testing this, not assumed working: OpenAI's TTS
    'wav' response is generated as a stream and writes the RIFF/data chunk
    sizes as the streaming placeholder 0xFFFFFFFF (length unknown at encode
    time) -- the stdlib wave module takes that field at face value, which
    turned a real ~2s clip into a reported ~24.8 DAY duration and wrongly
    forced the speed-correction path below to its 4x cap every time. The
    'fmt ' subchunk (channel count/sample width/frame rate) isn't affected,
    only the outer sizes are, so those three are still read the normal way
    and only the payload length is computed manually from what's actually
    in the buffer."""
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
        audio_bytes = _synthesize_once(text, speed=1.0)
        duration = _wav_duration_seconds(audio_bytes)
        speed_used = 1.0

        if duration > max_seconds:
            # Real, not hypothetical: a ~40-word answer at a natural
            # speaking rate can land at ~16-17s, over the 15s budget --
            # regenerate once at a proportionally faster speed rather than
            # silently shipping an over-budget clip. Capped to OpenAI's
            # documented speed range (0.25-4.0).
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
        # The openai SDK can raise several distinct error types (APIError,
        # RateLimitError, APIConnectionError, ...) -- wrapped into one typed
        # TTSError, same posture as asr.py's ASRError.
        raise TTSError(f"Speech synthesis failed: {e}") from e
