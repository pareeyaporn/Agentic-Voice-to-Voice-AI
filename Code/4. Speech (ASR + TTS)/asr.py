"""
ASR module (§4.1). Speech-to-text via faster-whisper, run locally -- free,
no API key/billing, same reasoning as §1.3's local embeddings.

Fragment-based: the UI (§5.1) records the full clip, this transcribes it in
one call. Streaming ASR is a stated stretch goal, not attempted.
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

from speech_config import ASR_COMPUTE_TYPE, ASR_DEVICE, ASR_MODEL_SIZE

_model = None  # lazy-loaded, process-wide singleton -- model load (~seconds) happens once, not per call


class ASRError(Exception):
    """Typed so a caller can branch on failure instead of catching a bare Exception."""

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
    """audio_path: a WAV/MP3/webm file path -- faster-whisper decodes all of
    these (via its bundled PyAV). Returns the transcript, per-segment
    timestamps, and detected language."""
    if not os.path.exists(audio_path):
        raise ASRError(f"Audio file not found: {audio_path}")

    try:
        model = _get_model()
        segments_iter, info = model.transcribe(audio_path)
        segments = [
            TranscriptSegment(text=s.text.strip(), start=s.start, end=s.end) for s in segments_iter
        ]
    except Exception as e:
        # faster-whisper/ctranslate2/PyAV raise several exception types -- normalized to one ASRError
        raise ASRError(f"Transcription failed: {e}") from e

    full_text = " ".join(s.text for s in segments).strip()
    return TranscriptionResult(
        text=full_text,
        segments=segments,
        language=info.language,
        language_probability=info.language_probability,
    )
