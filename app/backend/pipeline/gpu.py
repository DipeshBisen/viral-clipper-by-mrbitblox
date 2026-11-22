"""Checks whether a video can be decoded + resized on the NVIDIA GPU (NVDEC + scale_cuda).

RTX 20-series cards decode H.264 / HEVC / VP9 but not AV1 (common for YouTube downloads), so we
test each file once with a 1-frame decode and remember the answer."""
import subprocess
from pathlib import Path
from typing import Dict

import config

_CACHE: Dict[str, bool] = {}


def gpu_decode_ok(path: Path) -> bool:
    if config.VIDEO_HWACCEL in ("", "none"):
        return False
    key = str(path)
    if key not in _CACHE:
        cmd = ["ffmpeg", "-v", "error", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
               "-i", str(path), "-frames:v", "3", "-an", "-sn",
               "-vf", "scale_cuda=64:36:format=nv12,hwdownload,format=nv12", "-f", "null", "-"]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                 errors="replace", timeout=6)
            _CACHE[key] = res.returncode == 0 and "error" not in res.stderr.lower()
        except Exception:
            _CACHE[key] = False
    return _CACHE[key]
