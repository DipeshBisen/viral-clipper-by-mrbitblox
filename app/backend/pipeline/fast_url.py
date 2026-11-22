"""Audio-first processing for online videos (YouTube etc.).

Instead of downloading the whole video before doing anything:
  1. download only the audio track (a 35-min video is ~30 MB of audio vs ~1.2 GB of video),
  2. transcribe / analyse / score from that audio,
  3. download only the few seconds of video each chosen clip needs, in parallel,
  4. line each downloaded section up with the audio (cross-correlation), because a stream-copied
     section starts on the nearest keyframe, not at the exact second asked for.
"""
import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import config
from .download import VideoMetadata, _extract_heatmap_data, _get_video_duration, _ytdlp, _YT_FORMAT

logger = logging.getLogger("viral_clipper.fast_url")

SECTION_PAD = 2.5  # seconds of extra video fetched on each side of a clip
SR = 16000


def _run(cmd: List[str], timeout: Optional[float] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


async def fetch_audio(url: str, job_dir: Path, start: Optional[float] = None,
                      end: Optional[float] = None) -> VideoMetadata:
    """Download only the audio track (+ info json). With a range, cut the audio to it."""
    job_dir.mkdir(parents=True, exist_ok=True)
    has_range = start is not None and end is not None and end > start
    cmd = _ytdlp() + [
        "-f", "bestaudio[ext=m4a]/bestaudio",
        "--write-info-json", "--no-playlist", "--concurrent-fragments", "8",
        "--match-filter", "!is_live",  # live streams take the recording path instead
        "-o", str(job_dir / "audio_src.%(ext)s"),
    ]
    # Always fetch the whole audio track: YouTube serves partial (section) downloads at about
    # real-time speed, so even a 2-hour pick from a 23-hour stream is faster to get in full and cut.
    cmd.append(url)
    res = await asyncio.to_thread(_run, cmd)
    files = [p for p in job_dir.glob("audio_src.*") if p.suffix not in (".json", ".part")]
    if res.returncode != 0 or not files:
        raise RuntimeError(f"Audio download failed: {res.stderr.strip()[-300:]}")
    audio = files[0]

    info: Dict[str, Any] = {}
    info_json = job_dir / "audio_src.info.json"
    if info_json.exists():
        try:
            info = json.loads(info_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    offset = float(start) if has_range else 0.0
    if has_range:
        cut = job_dir / f"audio_section{audio.suffix}"
        await asyncio.to_thread(_ffmpeg_audio_cut, audio, cut, float(start), float(end))
        audio = cut

    heatmap = _extract_heatmap_data(info_json)
    if heatmap and has_range:
        heatmap = [{"start": h["start"] - offset, "end": h["end"] - offset, "value": h["value"]}
                   for h in heatmap if h["end"] > offset and h["start"] < float(end)] or None

    meta = VideoMetadata(source_path=audio, title=info.get("title") or "Video",
                         duration=_get_video_duration(audio), url=url, heatmap_data=heatmap)
    meta.offset = offset
    logger.info(f"Audio-first: got audio for '{meta.title}' ({meta.duration:.0f}s), video comes per clip")
    return meta


def _ffmpeg_audio_cut(src: Path, dst: Path, start: float, end: float) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{end - start:.3f}",
           "-vn", "-c", "copy", str(dst)]
    res = _run(cmd)
    if res.returncode != 0 or not dst.exists():
        raise RuntimeError(f"Could not cut audio range: {res.stderr[-300:]}")


class ClipVideoFetcher:
    """Downloads just the video sections needed for each clip and aligns them to the job timeline."""

    def __init__(self, url: str, job_dir: Path, offset: float, full_audio_wav: Path):
        self.url = url
        self.job_dir = job_dir
        self.offset = offset  # job timeline -> original video timeline
        self.full_audio_wav = full_audio_wav
        self._urls: Optional[List[str]] = None
        self._url_lock = asyncio.Lock()
        self._audio: Optional[np.ndarray] = None
        self._full_video: Optional[Path] = None
        self._full_lock = asyncio.Lock()

    async def _stream_urls(self) -> List[str]:
        async with self._url_lock:
            if self._urls is None:
                res = await asyncio.to_thread(_run, _ytdlp() + ["-g", "-f", _YT_FORMAT, "--no-playlist", self.url], 120)
                urls = [u for u in res.stdout.splitlines() if u.startswith("http")]
                if res.returncode != 0 or not urls:
                    raise RuntimeError(f"Could not get stream URLs: {res.stderr.strip()[-300:]}")
                self._urls = urls
            return self._urls

    def _job_audio(self) -> np.ndarray:
        if self._audio is None:
            import soundfile as sf
            data, sr = sf.read(str(self.full_audio_wav), dtype="float32")
            if data.ndim > 1:
                data = data.mean(axis=1)
            self._audio = data
        return self._audio

    async def get(self, idx: int, clip_start: float, clip_end: float) -> Tuple[Path, float]:
        """Return (video file, shift): render with start = clip_start - shift."""
        try:
            return await self._section(idx, clip_start, clip_end)
        except Exception as e:
            logger.warning(f"Clip {idx}: section download failed ({e}); falling back to full video download.")
            return await self._full(), 0.0

    async def _section(self, idx: int, clip_start: float, clip_end: float) -> Tuple[Path, float]:
        urls = await self._stream_urls()
        req_start = max(0.0, clip_start - SECTION_PAD)  # job timeline
        dur = (clip_end - req_start) + SECTION_PAD
        abs_start = req_start + self.offset
        out = self.job_dir / f"clipsrc_{idx:02d}.mp4"

        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{abs_start:.3f}", "-i", urls[0]]
        if len(urls) > 1:
            cmd += ["-ss", f"{abs_start:.3f}", "-i", urls[1], "-map", "0:v:0", "-map", "1:a:0"]
        cmd += ["-t", f"{dur:.3f}", "-c", "copy", "-avoid_negative_ts", "make_zero", str(out)]
        res = await asyncio.to_thread(_run, cmd, 300)
        if res.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            raise RuntimeError(res.stderr.strip()[-200:] or "empty section")

        actual_start = await asyncio.to_thread(self._align, out, req_start)
        if clip_start - actual_start < 0 or clip_end - actual_start > _get_video_duration(out) + 0.3:
            raise RuntimeError("section does not cover the clip")
        return out, actual_start

    def _align(self, section: Path, expected_start: float) -> float:
        """Return the job-timeline time of the section file's t=0.

        The video part of a stream-copied section starts on the keyframe BEFORE the requested time,
        while the audio part starts at (about) the requested time, so inside the file the audio begins
        `a_start` seconds after t=0. We confirm the exact position by matching the audio."""
        pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                             "stream=start_time", "-of", "csv=p=0", str(section)], capture_output=True, text=True)
        try:
            a_start = max(0.0, float(pr.stdout.strip().splitlines()[0]))
        except Exception:
            a_start = 0.0
        estimate = expected_start - a_start  # audio was cut accurately at expected_start

        snip_len, t_in = 8.0, a_start + 0.3
        res = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}", "-i", str(section), "-t", str(snip_len),
                              "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True)
        snip = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        full = self._job_audio()
        if len(snip) < SR * 2 or float(np.abs(snip).mean()) < 1e-4:
            return estimate  # silent / too short to match

        center = estimate + t_in  # where the snippet should sit in the job timeline
        w0 = max(0, int((center - 3.0) * SR))
        w1 = min(len(full), int((center + 3.0) * SR) + len(snip))
        window = full[w0:w1]
        if len(window) <= len(snip):
            return estimate
        n = 1 << int(np.ceil(np.log2(len(window) + len(snip))))
        corr = np.fft.irfft(np.fft.rfft(window, n) * np.conj(np.fft.rfft(snip, n)), n)[: len(window) - len(snip) + 1]
        csum = np.concatenate([[0.0], np.cumsum(window.astype(np.float64) ** 2)])
        energy = np.sqrt(csum[len(snip):] - csum[: len(window) - len(snip) + 1]) * np.linalg.norm(snip) + 1e-9
        score = corr / energy
        lag = int(np.argmax(score))
        if score[lag] < 0.5:
            return estimate
        return (w0 + lag) / SR - t_in

    async def _full(self) -> Path:
        async with self._full_lock:
            if self._full_video is None:
                from .download import download_video
                start = self.offset if self.offset else None
                end = None
                if start is not None:
                    end = start + _get_video_duration(self.full_audio_wav)
                meta = await download_video(self.url, self.job_dir / "full", start=start, end=end)
                self._full_video = meta.source_path
            return self._full_video
