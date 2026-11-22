"""LLM interface for scoring candidate viral clips with Google Gemini."""
import asyncio
import json
import logging
import warnings
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import config

logger = logging.getLogger("viral_clipper.llm")

class ClipJudgment(BaseModel):
    start: float = Field(..., description="Start timestamp of the clip in seconds")
    end: float = Field(..., description="End timestamp of the clip in seconds")
    duration: float = Field(..., description="Duration in seconds")
    title: str = Field(..., description="Catchy, high-CTR short title for the clip")
    hook_line: str = Field(..., description="The opening 3-second hook quote or phrase")
    score: int = Field(..., ge=0, le=100, description="Virality score from 0 to 100")
    viral_factors: List[str] = Field(default_factory=list, description="Keywords why it will perform, e.g. surprise, relatable, debate")
    reason: str = Field(..., description="1-2 sentences on why this clip will engage audiences")
    is_filler: bool = Field(False, description="Intro, outro, channel promo, or dead air: not a real moment")

def _init_gemini():
    if config.GEMINI_API_KEY:
        genai.configure(api_key=config.GEMINI_API_KEY)
    else:
        logger.warning("GEMINI_API_KEY not configured. LLM evaluations will use mock fallbacks.")

def _clean_json_str(text: str) -> str:
    """Strip markdown code fence blocks if returned."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def _heuristic_fallback(candidate: Dict[str, Any], min_duration: float, max_duration: float) -> ClipJudgment:
    """Guaranteed fallback when LLM is unavailable, rate-limited, or triggers safety filters."""
    sig_score = int(candidate.get("signal_score", 0.5) * 100)
    dur = round(candidate.get("end", 0.0) - candidate.get("start", 0.0), 2)
    dur = max(min_duration, min(max_duration, dur))
    
    text = candidate.get("text", "").strip()
    hook = text[:45] if text else "Watch this moment!"
    words = text.split()
    title = " ".join(words[:7]) + ("..." if len(words) > 7 else "") if words else "Watch this moment!"

    return ClipJudgment(
        start=candidate.get("start", 0.0),
        end=candidate.get("start", 0.0) + dur,
        duration=dur,
        title=title,
        hook_line=hook,
        score=min(95, max(45, sig_score)),
        viral_factors=["high_energy", "audience_reaction"],
        reason="Heuristic pick based on peak audio volume and viewer engagement heatmaps.",
    )

_SAFETY = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}


def _models_to_try() -> List[str]:
    models = [config.GEMINI_MODEL]
    if config.GEMINI_FALLBACK_MODEL and config.GEMINI_FALLBACK_MODEL not in models:
        models.append(config.GEMINI_FALLBACK_MODEL)
    return models


# When Google says a model's quota is used up (HTTP 429), stop calling that model for a while
# instead of waiting for timeouts on every job. {model_name: unix time it may be tried again}
_QUOTA_BLOCKED: Dict[str, float] = {}


def _is_quota_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "resourceexhausted" in type(e).__name__.lower()


def gemini_available() -> bool:
    """False while every configured Gemini model is quota-blocked (callers can skip Gemini)."""
    import time
    return bool(config.GEMINI_API_KEY) and any(
        _QUOTA_BLOCKED.get(m, 0) <= time.time() for m in _models_to_try())


def _generate_json(prompt: str, timeout: float) -> Any:
    """Call Gemini (primary model, then fallback model) and parse a JSON response.
    Every request has a hard timeout: the SDK otherwise retries 5xx silently for ~10 minutes.
    Quota errors (429) are not retried, and that model is skipped for QUOTA_COOLDOWN_SEC."""
    import time
    from google.api_core import exceptions as gexc
    from google.api_core import retry as api_retry
    _init_gemini()
    # Retry only real hiccups (server busy / errors), never "quota exceeded"
    retry = api_retry.Retry(
        predicate=api_retry.if_exception_type(gexc.ServiceUnavailable, gexc.InternalServerError),
        initial=1.0, maximum=4.0, timeout=timeout,
    )
    last_err: Optional[Exception] = None
    for name in _models_to_try():
        blocked_until = _QUOTA_BLOCKED.get(name, 0)
        if blocked_until > time.time():
            last_err = RuntimeError(f"{name} quota exceeded (skipping for {int(blocked_until - time.time())}s)")
            continue
        try:
            model = genai.GenerativeModel(name, safety_settings=_SAFETY)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"},
                request_options={"timeout": timeout, "retry": retry},
            )
            return json.loads(_clean_json_str(response.text))
        except Exception as e:
            last_err = e
            if _is_quota_error(e):
                _QUOTA_BLOCKED[name] = time.time() + config.QUOTA_COOLDOWN_SEC
                logger.warning(f"Gemini ({name}) quota exceeded; skipping it for "
                               f"{config.QUOTA_COOLDOWN_SEC // 60} min")
            else:
                logger.warning(f"Gemini ({name}) failed: {str(e)[:200]}")
    raise RuntimeError(f"All Gemini models failed: {last_err}")


def _clamp_judgment(data: Dict[str, Any], candidate: Dict[str, Any],
                    min_duration: float, max_duration: float) -> ClipJudgment:
    start = float(data.get("start", candidate.get("start", 0.0)))
    end = float(data.get("end", candidate.get("end", start + min_duration)))
    # Keep the LLM inside (roughly) the candidate window it was shown
    if not (candidate.get("start", 0.0) - 5 <= start <= candidate.get("end", start) + 5):
        start = float(candidate.get("start", 0.0))
        end = float(candidate.get("end", start + max_duration))
    duration = min(max_duration, max(min_duration, end - start))
    return ClipJudgment(
        start=round(start, 2),
        end=round(start + duration, 2),
        duration=round(duration, 2),
        title=str(data.get("title") or _heuristic_fallback(candidate, min_duration, max_duration).title),
        hook_line=str(data.get("hook_line") or ""),
        score=int(max(0, min(100, int(data.get("score", 50))))),
        viral_factors=[str(v) for v in (data.get("viral_factors") or [])][:6],
        reason=str(data.get("reason") or ""),
        is_filler=bool(data.get("is_filler", False)),
    )


def _title_language_rule(language: str) -> str:
    if config.CAPTION_SCRIPT == "roman" and language in ("hi", "ur", ""):
        return ('Write "title" and "hook_line" in HINGLISH: Hindi and English words mixed, written ONLY '
                'in Latin/English letters (e.g. "Bhai ye kya ho gaya", "Kal milte hain"). '
                'Never use Devanagari, and never fully translate into English.')
    return (f'Write "title" and "hook_line" in the SAME language and script as the transcript '
            f'(spoken language code: "{language or "unknown"}"). Do NOT translate to English.')


def _title_examples(language: str) -> str:
    if config.CAPTION_SCRIPT == "roman" and language in ("hi", "ur", ""):
        return '"BHAI YE KYA HO GAYA", "SABSE DARAWNA JUMPSCARE", "SPEED PLAYS GTA 6"'
    return '"HE DID NOT SEE THAT COMING", "SPEED PLAYS GTA 6", "THE SCARIEST JUMPSCARE EVER"'


def _batch_prompt(candidates: List[Dict[str, Any]], min_duration: float, max_duration: float,
                  language: str) -> str:
    blocks = []
    for i, c in enumerate(candidates):
        blocks.append(
            f"""### Candidate {i}
- Proposed Range: {c.get('start', 0.0):.2f}s to {c.get('end', 0.0):.2f}s
- Context Before: "{c.get('context_before', '')}"
- Clip Transcript: "{c.get('text', '')}"
- Context After: "{c.get('context_after', '')}"
- Raw Signal Score: {c.get('signal_score', 0.5):.2f}"""
        )
    return f"""You are an elite short-form video editor for TikTok, YouTube Shorts, and Instagram Reels.
Below are {len(candidates)} candidate moments from one video/stream. Judge EACH one for how well it would
work as a viral standalone short.

Rules:
1. Clip duration MUST be between {min_duration:.1f} and {max_duration:.1f} seconds, inside or near the proposed range.
2. Reward a strong hook in the first 3 seconds (punchline, surprise, controversy, big reaction, conflict).
3. The clip must make sense on its own and end cleanly (punchline, laughter, conclusion, cliffhanger).
4. Use the full 0-100 score range so the best moments clearly stand out.
   Score below 30 if the moment is boring, unintelligible, or has no clear payoff.
5. Set "is_filler": true for the video's intro ("aaj ki video mein...", "video ko end tak dekhna"),
   outro ("milte hain agli video mein", "thanks for watching"), like/subscribe/comment/playlist promos,
   sponsor reads, loading screens, or dead air, ONLY when that is MOST of the clip.
   Any real gameplay/reaction moment (even with a little intro talk mixed in) is NOT filler: false.
6. {_title_language_rule(language)}
   Titles: short (max ~7 words), curiosity-driven, scroll-stopping, like a gaming/streamer
   shorts headline (e.g. {_title_examples(language)}); 1 emoji max.

{chr(10).join(blocks)}

Return STRICT JSON: an array with exactly one object per candidate:
[{{"id": int (candidate number), "start": float, "end": float, "title": str, "hook_line": str,
   "score": int, "viral_factors": [str], "reason": str, "is_filler": bool}}]
"""


def judge_candidate(
    candidate: Dict[str, Any],
    min_duration: float = config.DEFAULT_CLIP_MIN_DURATION,
    max_duration: float = config.DEFAULT_CLIP_MAX_DURATION,
    language: str = "",
) -> ClipJudgment:
    """Judge a single candidate (blocking). Falls back to a heuristic pick on any failure."""
    if not config.GEMINI_API_KEY:
        return _heuristic_fallback(candidate, min_duration, max_duration)
    try:
        data = _generate_json(_batch_prompt([candidate], min_duration, max_duration, language),
                              config.LLM_TIMEOUT_SEC)
        if isinstance(data, list):
            data = data[0] if data else {}
        return _clamp_judgment(data, candidate, min_duration, max_duration)
    except Exception:
        return _heuristic_fallback(candidate, min_duration, max_duration)


async def judge_candidates(
    candidates: List[Dict[str, Any]],
    min_duration: float = config.DEFAULT_CLIP_MIN_DURATION,
    max_duration: float = config.DEFAULT_CLIP_MAX_DURATION,
    language: str = "",
) -> List[ClipJudgment]:
    """Judge all candidates in ONE Gemini request (fast, rate-limit friendly, and the model can
    compare moments against each other). Any candidate the model skips gets a heuristic pick."""
    if not candidates:
        return []
    results: Dict[int, ClipJudgment] = {}
    if config.GEMINI_API_KEY:
        prompt = _batch_prompt(candidates, min_duration, max_duration, language)
        try:
            data = await asyncio.to_thread(_generate_json, prompt, config.LLM_TIMEOUT_SEC)
            if isinstance(data, dict):
                data = data.get("candidates") or data.get("clips") or [data]
            for pos, item in enumerate(data if isinstance(data, list) else []):
                if not isinstance(item, dict):
                    continue
                idx = int(item.get("id", pos)) if str(item.get("id", pos)).isdigit() else pos
                if 0 <= idx < len(candidates) and idx not in results:
                    results[idx] = _clamp_judgment(item, candidates[idx], min_duration, max_duration)
            logger.info(f"Gemini judged {len(results)}/{len(candidates)} candidates in one request")
        except Exception as e:
            logger.warning(f"Batched Gemini judging failed, using heuristic picks: {e}")
    else:
        logger.warning("GEMINI_API_KEY not set; using heuristic picks.")

    judgments = [results.get(i) or _heuristic_fallback(c, min_duration, max_duration)
                 for i, c in enumerate(candidates)]
    judgments.sort(key=lambda j: j.score, reverse=True)
    return judgments
