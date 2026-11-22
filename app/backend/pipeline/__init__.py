"""Pipeline package for viral-clipper.

Provides end-to-end video processing functions: downloading, transcription,
signal analysis, scoring, reframing, caption generation, and final export.
"""

from .download import download_video
from .transcribe import transcribe_video
from .analyze import analyze_signals
from .score import score_and_rank
from .reframe import reframe_clip
from .caption import generate_captions
from .export import export_clip, export_all_clips

__all__ = [
    "download_video",
    "transcribe_video",
    "analyze_signals",
    "score_and_rank",
    "reframe_clip",
    "generate_captions",
    "export_clip",
    "export_all_clips",
]
