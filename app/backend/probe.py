"""Print a JSON description of a video URL or local file (title, length, live status).
Used by the web UI before a job starts:  python probe.py <url-or-path>"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pipeline.download import probe_source  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: probe.py <url-or-path>"}))
        sys.exit(2)
    try:
        print(json.dumps(probe_source(sys.argv[1]), ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"error": str(e)[:400]}, ensure_ascii=False))
        sys.exit(1)
