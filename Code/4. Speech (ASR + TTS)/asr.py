"""
ASR module (§4.1). Speech-to-text via faster-whisper, run locally -- free,
no API key/billing, same cost-conscious reasoning as §1.3's local
sentence-transformers embeddings (confirmed with the user before adding as
a new dependency, per the project's tech-confirmation convention).

.py per the file-format convention (reason (c): the UI (§5, not yet built)
will import transcribe() directly at query time -- once per mic recording,
not a one-shot notebook run).

Fragment-based only: the full clip is recorded first (the UI's job, §5.1),
then transcribed in one call here. Streaming ASR is the backlog's own
stated stretch goal, not attempted.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

from config import ASR_COMPUTE_TYPE, ASR_DEVICE, ASR_MODEL_SIZE

_model = None  # lazy-loaded, process-wide singleton: model load (~seconds)
# is the expensive part, so it happens once per process, not once per call --
# same reasoning as §2's persistent MCP session (pay startup cost once, not
# per query).


class ASRError(Exception):
    """Typed so a caller (the UI, §5) can branch on failure instead of
    catching a bare Exception -- same error-handling posture as §3.4's
    ToolError."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float


@dataclass
class TranscriptionResult:
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    language: Optional[str] = None
    language_probability: Optional[float] = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(ASR_MODEL_SIZE, device=ASR_DEVICE, compute_type=ASR_COMPUTE_TYPE)
    return _model


def transcribe(audio_path: str) -> TranscriptionResult:
    """audio_path: a WAV/MP3 file path (whatever the UI's mic capture wrote
    to disk) -- faster-whisper decodes both, and anything else its bundled
    PyAV can read, through the same call. Returns the full transcript text
    plus per-segment timestamps and the detected language."""
    if not os.path.exists(audio_path):
        raise ASRError(f"Audio file not found: {audio_path}")

    try:
        model = _get_model()
        segments_iter, info = model.transcribe(audio_path)
        segments = [
            TranscriptSegment(text=s.text.strip(), start=s.start, end=s.end) for s in segments_iter
        ]
    except Exception as e:
        # faster-whisper/ctranslate2/PyAV can raise several distinct
        # exception types for a bad/corrupt/unsupported file -- wrapped into
        # one typed ASRError rather than the caller needing to know all of
        # them.
        raise ASRError(f"Transcription failed: {e}") from e

    full_text = " ".join(s.text for s in segments).strip()
    return TranscriptionResult(
        text=full_text,
        segments=segments,
        language=info.language,
        language_probability=info.language_probability,
    )
