"""Always-on local backend: keeps the Whisper model loaded in memory so each job starts instantly.

    python server.py            # listens on http://127.0.0.1:8765 (this PC only)

Endpoints (used by the web app; it starts this server automatically when needed):
    GET  /health                -> {"ok": true, "model_ready": bool, "queued": n, "running": job_id|null}
    GET  /probe?source=...      -> video title / length / live status
    POST /jobs   {job_id, source, ...run_pipeline options}  -> {"queued": true}

Jobs run one at a time (they share the GPU), in arrival order.
"""
import asyncio
import inspect
import json
import logging
import queue
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config  # noqa: E402
from app import run_pipeline, update_status  # noqa: E402
from pipeline.download import probe_source  # noqa: E402

HOST, PORT = "127.0.0.1", 8765
logger = logging.getLogger("viral_clipper.server")

_jobs: "queue.Queue[dict]" = queue.Queue()
_state = {"model_ready": False, "running": None}
_PIPELINE_ARGS = set(inspect.signature(run_pipeline).parameters)


def _warm_up() -> None:
    """Load Whisper (and check the GPU encoder) before the first job arrives."""
    try:
        from pipeline.transcribe import _load_model, _language_id_model
        from pipeline.reframe import _video_encoder_args
        model, device = _load_model()
        _language_id_model(model, device)  # auto-detect (Hinglish vs English) costs no load time
        # The "best" Hindi model (large-v3) loads on the first job that asks for it.
        _video_encoder_args()
        _state["model_ready"] = True
        logger.info("Warm-up done: speech model is loaded and ready.")
    except Exception as e:
        logger.warning(f"Warm-up failed (jobs will still load the model on demand): {e}")


def _worker() -> None:
    while True:
        job = _jobs.get()
        job_id = job["job_id"]
        _state["running"] = job_id
        job_dir = config.DATA_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(job_dir / "process.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)
        try:
            kwargs = {k: v for k, v in job.items() if k in _PIPELINE_ARGS}
            asyncio.run(run_pipeline(**kwargs))
        except Exception as e:  # run_pipeline normally reports its own failures
            logger.exception(f"Job {job_id} crashed: {e}")
            update_status(job_id, "Failed", 0, status="failed", error=str(e))
        finally:
            logging.getLogger().removeHandler(handler)
            handler.close()
            _state["running"] = None
            _jobs.task_done()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep the console quiet
        pass

    def do_GET(self) -> None:
        url = urlparse(self.path)
        if url.path == "/health":
            return self._send(200, {"ok": True, "model_ready": _state["model_ready"],
                                    "queued": _jobs.qsize(), "running": _state["running"]})
        if url.path == "/probe":
            source = (parse_qs(url.query).get("source") or [""])[0]
            if not source:
                return self._send(400, {"error": "Missing source"})
            try:
                return self._send(200, probe_source(source))
            except Exception as e:
                return self._send(422, {"error": str(e)[:400]})
        self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/jobs":
            return self._send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            job = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._send(400, {"error": "Invalid JSON"})
        if not job.get("job_id") or not job.get("source"):
            return self._send(400, {"error": "job_id and source are required"})
        if not str(job["job_id"]).replace("_", "").isalnum():
            return self._send(400, {"error": "Invalid job_id"})
        update_status(job["job_id"], "Queued", 2, status="processing")
        _jobs.put(job)
        self._send(200, {"queued": True, "position": _jobs.qsize()})


def main() -> None:
    threading.Thread(target=_warm_up, daemon=True).start()
    threading.Thread(target=_worker, daemon=True).start()
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Viral Clipper backend is already running on http://{HOST}:{PORT}")
        return
    print(f"Viral Clipper backend ready on http://{HOST}:{PORT} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
