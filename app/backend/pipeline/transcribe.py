"""Audio extraction and speech-to-text with faster-whisper (word timestamps).

Speed notes:
- Runs on the NVIDIA GPU automatically when one is usable (float16, batched inference).
- The Whisper model is loaded once per process and reused.
- Greedy decoding (beam_size=1) by default.

Script notes:
- Captions keep the language's native script (Hindi stays in Devanagari) unless
  config.CAPTION_SCRIPT == "roman", in which case Hindi is converted to Hinglish.
"""
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Tuple
import config

logger = logging.getLogger("viral_clipper.transcribe")

# Bump when the transcript format/content rules change so stale caches are regenerated.
CACHE_VERSION = 4

# Optional code-mixed prompt (config.CODE_MIXED_PROMPT) nudging Whisper to keep English
# words in Latin letters inside Devanagari Hindi.
LANGUAGE_PROMPTS = {
    "hi": "नमस्ते दोस्तों, आज हम एक नया game खेलेंगे। ये setup बहुत अच्छा है, चलो start करते हैं।",
}

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    confidence: float

@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: List[WordTimestamp]

@dataclass
class TranscriptionResult:
    segments: List[TranscriptSegment]
    language: str
    full_text: str


def _register_nvidia_dll_dirs() -> None:
    """On Windows, make pip-installed CUDA libs (nvidia-cublas-cu12, nvidia-cudnn-cu12) loadable."""
    if os.name != "nt":
        return
    try:
        import nvidia  # namespace package from the nvidia-* wheels
    except ImportError:
        return
    for base in getattr(nvidia, "__path__", []):
        for sub in ("cublas", "cudnn", "cuda_nvrtc", "cuda_runtime"):
            bin_dir = Path(base) / sub / "bin"
            if bin_dir.is_dir():
                try:
                    os.add_dll_directory(str(bin_dir))
                except OSError:
                    pass
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


_MODEL_CACHE: dict = {}


def _resolve_device() -> str:
    device = config.WHISPER_DEVICE
    if device != "auto":
        return device
    try:
        import ctranslate2
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def _load_model(name_override: Optional[str] = None, compute_override: Optional[str] = None):
    """Load (or reuse) the Whisper model, falling back to CPU if the GPU can't be used."""
    from faster_whisper import WhisperModel

    _register_nvidia_dll_dirs()
    device = _resolve_device()

    attempts = [device] if device == "cpu" else [device, "cpu"]
    last_err: Optional[Exception] = None
    for dev in attempts:
        model_name = name_override if (name_override and dev == "cuda") else config.WHISPER_MODEL
        if model_name == "auto":
            model_name = "large-v3-turbo" if dev == "cuda" else "small"
        compute_type = compute_override if (compute_override and dev == "cuda") else config.WHISPER_COMPUTE_TYPE
        if compute_type == "default":
            compute_type = "float16" if dev == "cuda" else "int8"

        key = (model_name, dev, compute_type)
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key], dev
        try:
            logger.info(f"Loading faster-whisper ({model_name}) on {dev} [{compute_type}]...")
            model = WhisperModel(model_name, device=dev, compute_type=compute_type)
            if dev == "cuda":
                # Encode a tiny silent clip to confirm cuBLAS/cuDNN actually load.
                import numpy as np
                list(model.transcribe(np.zeros(16000, dtype="float32"), beam_size=1, language="en")[0])
            _MODEL_CACHE[key] = model
            return model, dev
        except Exception as e:
            last_err = e
            logger.warning(f"Whisper on {dev} unavailable ({e}). "
                           + ("Falling back to CPU." if dev != "cpu" else ""))
    raise RuntimeError(f"Could not load Whisper model: {last_err}")


def _extract_audio(video_path: Path, job_dir: Path) -> Path:
    """Extract audio track as 16kHz mono WAV for Whisper."""
    audio_path = job_dir / "audio.wav"
    if audio_path.exists():
        return audio_path

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(audio_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        logger.error(f"FFmpeg audio extraction failed: {res.stderr}")
        raise RuntimeError("Failed to extract audio track from video.")
    return audio_path


def _load_cache(transcript_cache: Path, language: str, script: str, quality: str = "fast") -> Optional[TranscriptionResult]:
    if not transcript_cache.exists():
        return None
    try:
        with open(transcript_cache, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("cache_version") != CACHE_VERSION or data.get("script") != script:
            return None
        if language != "auto" and data.get("requested_language") != language:
            return None
        if data.get("language") in INDIC_LANGS and data.get("quality", "fast") != quality:
            return None
        segments = []
        for seg in data["segments"]:
            words = _collapse_phrase_loops([WordTimestamp(**w) for w in seg["words"]])
            text = " ".join(w.word for w in words) if words else seg["text"]
            segments.append(TranscriptSegment(text=text, start=seg["start"], end=seg["end"], words=words))
        logger.info("Using cached transcript.")
        return TranscriptionResult(segments=segments, language=data["language"], full_text=data["full_text"])
    except Exception:
        return None


INDIC_LANGS = {"hi", "mr", "bn", "pa", "gu", "ta", "te", "kn", "ml", "ne", "ur"}


def _language_id_model(main_model, device: str):
    """large-v3-turbo has poor language ID (it calls Hindi/Hinglish 'en'), so use the
    small multilingual model just for detection. Cached; ~0.5 GB."""
    if "turbo" not in str(config.WHISPER_MODEL) and config.WHISPER_MODEL != "auto":
        return main_model
    key = ("small", device, "langid")
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel
        try:
            _MODEL_CACHE[key] = WhisperModel("small", device=device,
                                             compute_type="float16" if device == "cuda" else "int8")
        except Exception as e:
            logger.warning(f"Language-ID model unavailable ({e}); using main model.")
            _MODEL_CACHE[key] = main_model
    return _MODEL_CACHE[key]


def _detect_language(model, audio_path: Path, windows: int = 8) -> str:
    """Vote over several 30s windows spread across the video instead of only the first 30s
    (streams often open with English chit-chat). Hinglish speech is frequently labelled 'en',
    so an Indic language that wins a fair share of windows is preferred over English."""
    from collections import Counter
    from faster_whisper.audio import decode_audio

    sr = 16000
    audio = decode_audio(str(audio_path), sampling_rate=sr)
    win = 30 * sr
    if len(audio) <= win:
        starts = [0]
    else:
        n = min(windows, max(1, len(audio) // win))
        starts = [int(i * (len(audio) - win) / max(1, n - 1)) for i in range(n)]

    votes: Counter = Counter()
    for st in starts:
        chunk = audio[st:st + win]
        if float((chunk ** 2).mean()) < 1e-6:  # silence
            continue
        lang, prob, _ = model.detect_language(chunk)
        if lang == "ur":  # Whisper often labels spoken Hindi as Urdu
            lang = "hi"
        votes[lang] += prob

    if not votes:
        return "en"
    total = sum(votes.values())
    best = votes.most_common(1)[0][0]
    indic = [(l, v) for l, v in votes.most_common() if l in INDIC_LANGS]
    if best == "en" and indic and indic[0][1] >= 0.25 * total:
        best = indic[0][0]
    logger.info("Language votes: " + ", ".join(f"{l}={v / total:.0%}" for l, v in votes.most_common(4))
                + f" -> '{best}'")
    return best


def _collapse_repeats(words: List[WordTimestamp], max_run: int = 2) -> List[WordTimestamp]:
    """Drop Whisper hallucination loops like 'no no no no no no ...' (keep at most max_run)."""
    out: List[WordTimestamp] = []
    run = 0
    for w in words:
        key = w.word.strip(".,!?।").lower()
        if out and key and key == out[-1].word.strip(".,!?।").lower():
            run += 1
            if run >= max_run:
                out[-1].end = max(out[-1].end, w.end)
                continue
        else:
            run = 0
        out.append(w)
    return out


def _collapse_phrase_loops(words: List[WordTimestamp], max_repeats: int = 2) -> List[WordTimestamp]:
    """Drop hallucinated phrase loops like 'rukh jo rukh jo rukh jo ...' (2-4 word phrases
    repeated back to back). Keeps the first `max_repeats` copies."""
    def key(w: WordTimestamp) -> str:
        return w.word.strip(".,!?।").lower()

    out = list(words)
    for n in (6, 5, 4, 3, 2):
        i, result = 0, []
        while i < len(out):
            phrase = [key(w) for w in out[i:i + n]]
            reps = 1
            while len(phrase) == n and [key(w) for w in out[i + reps * n:i + (reps + 1) * n]] == phrase:
                reps += 1
            if reps > max_repeats:
                kept = out[i:i + max_repeats * n]
                kept[-1].end = max(kept[-1].end, out[i + reps * n - 1].end)
                result.extend(kept)
                i += reps * n
            else:
                result.append(out[i])
                i += 1
        out = result
    return out


def _run_whisper(audio_path: Path, language: Optional[str], quality: str = "fast") -> Tuple[list, object]:
    model, device = _load_model()
    kwargs = dict(
        beam_size=config.WHISPER_BEAM_SIZE,
        word_timestamps=True,
        task="transcribe",  # never translate
        vad_filter=True,
        language=language,
    )

    # Language detection first, so we can lock the language (Whisper must never
    # translate) and apply a script-steering prompt.
    if language is None:
        try:
            kwargs["language"] = _detect_language(_language_id_model(model, device), audio_path)
        except Exception as e:
            logger.warning(f"Language pre-detection failed ({e}); letting Whisper decide.")

    # Opt-in: tends to keep English words in Latin letters, but on noisy audio it can make
    # Whisper loop or skip speech, so it is off by default.
    # Hindi & other Indian languages: turbo tends to loop ("guard guard guard...") on noisy gaming
    # audio. A repetition penalty fixes most of that at no speed cost ("fast").
    # "best" switches to the full large-v3 model: far more accurate on Hindi, ~4x slower.
    # English is untouched (turbo, no penalty).
    if kwargs.get("language") in INDIC_LANGS:
        kwargs["repetition_penalty"] = 1.15
        if quality == "best" and device == "cuda" and config.WHISPER_MODEL_INDIC:
            try:
                model, device = _load_model(config.WHISPER_MODEL_INDIC, config.WHISPER_INDIC_COMPUTE)
                logger.info(f"Best quality: using {config.WHISPER_MODEL_INDIC} for {kwargs['language']}")
            except Exception as e:
                logger.warning(f"Could not load {config.WHISPER_MODEL_INDIC} ({e}); using the fast model.")

    prompt = LANGUAGE_PROMPTS.get(kwargs.get("language") or "") if config.CODE_MIXED_PROMPT else None
    if prompt:
        kwargs["initial_prompt"] = prompt

    if device == "cuda" and config.WHISPER_BATCH_SIZE > 1:
        from faster_whisper import BatchedInferencePipeline
        pipeline = BatchedInferencePipeline(model=model)
        logger.info(f"Transcribing on GPU (batched x{config.WHISPER_BATCH_SIZE}, language={kwargs['language']})...")
        segments, info = pipeline.transcribe(str(audio_path), batch_size=config.WHISPER_BATCH_SIZE, **kwargs)
    else:
        kwargs["vad_parameters"] = dict(min_silence_duration_ms=1200, speech_pad_ms=500)
        logger.info(f"Transcribing on {device} (language={kwargs['language']})...")
        segments, info = model.transcribe(str(audio_path), **kwargs)
    return list(segments), info


async def transcribe_video(video_path: Path, job_dir: Path, language: Optional[str] = None,
                           quality: str = "fast") -> TranscriptionResult:
    """Transcribe video using faster-whisper with word-level timestamps."""
    import asyncio

    language = (language or config.TRANSCRIBE_LANGUAGE or "auto").lower()
    script = config.CAPTION_SCRIPT
    transcript_cache = job_dir / "transcript.json"
    quality = "best" if quality == "best" else "fast"
    cached = _load_cache(transcript_cache, language, script, quality)
    if cached:
        return cached

    audio_path = _extract_audio(video_path, job_dir)
    # Run the heavy, blocking work off the event loop so other stages can overlap.
    whisper_segments, info = await asyncio.to_thread(
        _run_whisper, audio_path, None if language == "auto" else language, quality
    )

    roman = script == "roman"

    # Pass 1: collect words per segment (still in the language's native script)
    raw_segments = []
    for s in whisper_segments:
        words = [
            WordTimestamp(word=w.word.replace("�", "").strip(), start=round(w.start, 2),
                          end=round(w.end, 2), confidence=round(w.probability, 2))
            for w in (s.words or []) if w.word.replace("�", "").strip()
        ]
        raw_segments.append((s, _collapse_phrase_loops(_collapse_repeats(words))))

    # Pass 2 (Hinglish): convert every word of the transcript in one batch, keeping
    # one output word per input word so the timestamps stay aligned.
    if roman:
        from .hinglish import transliterate_words, transliterate_to_hinglish
        flat = [w for _, ws in raw_segments for w in ws
                if any("ऀ" <= ch <= "ॿ" for ch in w.word)]  # only Devanagari words need it
        if flat:
            converted = await asyncio.to_thread(transliterate_words, [w.word for w in flat])
            for w, text in zip(flat, converted):
                w.word = text
        if flat:
            logger.info(f"Converted {len(flat)} Hindi words to Hinglish (Latin script)")

    result_segments: List[TranscriptSegment] = []
    full_text_parts = []
    for s, words in raw_segments:
        words = [w for w in words if w.word]
        if not words and not s.text.strip():
            continue
        seg_text = " ".join(w.word for w in words) if words else s.text.strip()
        if roman and not words:
            seg_text = transliterate_to_hinglish(seg_text)
        result_segments.append(TranscriptSegment(
            text=seg_text, start=round(s.start, 2), end=round(s.end, 2), words=words
        ))
        full_text_parts.append(seg_text)

    result = TranscriptionResult(
        segments=result_segments,
        language=info.language,
        full_text=" ".join(full_text_parts)
    )

    with open(transcript_cache, "w", encoding="utf-8") as f:
        json.dump({
            "cache_version": CACHE_VERSION,
            "script": script,
            "requested_language": language,
            "quality": quality,
            "language": result.language,
            "full_text": result.full_text,
            "segments": [
                {"text": s.text, "start": s.start, "end": s.end, "words": [asdict(w) for w in s.words]}
                for s in result.segments
            ]
        }, f, indent=2, ensure_ascii=False)

    logger.info(f"Transcription complete: {len(result_segments)} segments in {result.language}")
    return result
