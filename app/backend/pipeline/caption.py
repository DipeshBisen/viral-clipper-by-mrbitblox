"""
Word-by-word animated ASS captions in 9 styles, plus a burned-in title label.
Features:
- Continuation token merging (Whisper token repair)
- Character & duration budgeting (max_chars=18, max_duration=1.4s, strictly 1 line)
- Smooth hardware-accelerated zoom pop animation (\t(0,110,\fscx108\fscy108))
- Zero-gap, flicker-free event transitions
- Hormozi progressive word reveal (unspoken words rendered with transparent spacing)
- Layout-aware safe margins (split-cam seam at Y=960, mobile safe zone at Y=280)
- Native-script captions (Hindi in Devanagari) with per-word font switching:
  English words keep the Latin font, Indic words use a font that has their glyphs
- UTF-8 with BOM (utf-8-sig) for Windows libass reliability
"""
import logging
import math
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import config
from .transcribe import WordTimestamp

logger = logging.getLogger("viral_clipper.caption")

def _ass_time(seconds: float) -> str:
    """Format seconds into ASS timestamp H:MM:SS.cc (centiseconds)."""
    seconds = max(0.0, seconds)
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{hrs}:{mins:02d}:{secs:02d}.{cs:02d}"

def _escape_ass_text(text: str) -> str:
    """Neutralize characters that would interfere with ASS override tags or line breaks."""
    return (
        str(text or "")
        .replace("\\", "/")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\r", " ")
        .replace("\n", " ")
        .strip()
    )

# Unicode ranges -> script key in config.CAPTION_SCRIPT_FONTS
_SCRIPT_RANGES = [
    (0x0900, 0x097F, "devanagari"), (0xA8E0, 0xA8FF, "devanagari"),
    (0x0980, 0x09FF, "bengali"), (0x0A00, 0x0A7F, "gurmukhi"), (0x0A80, 0x0AFF, "gujarati"),
    (0x0B80, 0x0BFF, "tamil"), (0x0C00, 0x0C7F, "telugu"), (0x0C80, 0x0CFF, "kannada"),
    (0x0D00, 0x0D7F, "malayalam"), (0x0600, 0x06FF, "arabic"),
    (0x3040, 0x30FF, "cjk"), (0x4E00, 0x9FFF, "cjk"), (0xAC00, 0xD7AF, "cjk"),
]
_SENTENCE_END = (".", "!", "?", ",", "।", "॥", "؟", "。", "！", "？", "，")


def _word_script(text: str) -> Optional[str]:
    """Return the non-Latin script a word is written in, or None for Latin/other."""
    for ch in text:
        cp = ord(ch)
        for lo, hi, name in _SCRIPT_RANGES:
            if lo <= cp <= hi:
                return name
    return None


def _font_override(text: str, size: int) -> str:
    """ASS override tags selecting a font that can render this word ("" for Latin words).
    Indic fonts render visually smaller than Arial Black, so they get a slightly larger size."""
    script = _word_script(text)
    font = config.CAPTION_SCRIPT_FONTS.get(script) if script else None
    return f"\\fn{font}\\fs{size}" if font else ""


def _merge_continuation_words(words: List[WordTimestamp]) -> List[WordTimestamp]:
    """
    Merge faster-whisper continuation fragments onto their base word.
    Handles broken subwords, apostrophes, and punctuation (e.g. "don" + "'t" -> "don't").
    """
    merged: List[WordTimestamp] = []
    for w in words:
        text = w.word.strip()
        # Only glue true fragments: "'t", "'s", or a bare punctuation token like "," / "।"
        is_fragment = bool(text) and (text[0] in "'’" or all(not c.isalnum() for c in text))
        if merged and is_fragment:
            prev = merged[-1]
            prev.word = f"{prev.word}{text}"
            if w.end > prev.end:
                prev.end = w.end
        else:
            merged.append(WordTimestamp(word=text.strip(), start=w.start, end=w.end, confidence=w.confidence))
    return merged

def _collect_word_blocks(
    words: List[WordTimestamp],
    max_chars: int = 16,
    max_duration: float = 1.4
) -> List[List[WordTimestamp]]:
    """
    Group words into short, punchy 1-line blocks suitable for 9:16 vertical video.
    Each block stays on screen for at most max_duration seconds (default 1.4s)
    and stays within max_chars (default 16 chars).
    """
    blocks: List[List[WordTimestamp]] = []
    current_block: List[WordTimestamp] = []
    block_start: Optional[float] = None

    for w in words:
        if not current_block:
            current_block = [w]
            block_start = w.start
            continue

        curr_chars = sum(len(x.word) + 1 for x in current_block)
        duration = w.end - (block_start or w.start)

        # Break block early if:
        # 1. Total chars exceeds max_chars
        # 2. Block duration exceeds max_duration
        # 3. Previous word ended with punctuation
        prev_has_punct = current_block[-1].word.endswith(_SENTENCE_END)
        if curr_chars + len(w.word) > max_chars or duration > max_duration or prev_has_punct:
            blocks.append(current_block)
            current_block = [w]
            block_start = w.start
        else:
            current_block.append(w)

    if current_block:
        blocks.append(current_block)
    return blocks

def _rgb(hex_rgb: str, alpha: int = 0) -> str:
    """'FFE500' -> ASS colour &HAABBGGRR& (alpha 0 = opaque, 255 = invisible)."""
    r, g, b = hex_rgb[0:2], hex_rgb[2:4], hex_rgb[4:6]
    return f"&H{alpha:02X}{b}{g}{r}&".upper().replace("&H", "&H")


WHITE, BLACK = _rgb("FFFFFF"), _rgb("000000")

# ── Caption styles ──────────────────────────────────────────────────────────────
# mode:  chunk     = 1-3 words shown together in one colour, the spoken word pops (streamer clips)
#        highlight = words shown together, the spoken word changes colour + pops
#        single    = one big word at a time (MrBeast-style), colour cycles per word
#        karaoke   = words fill with colour as they are spoken
# char_w: average glyph width in em for uppercase text (used to keep lines inside the frame)
CAPTION_STYLES: Dict[str, Dict[str, Any]] = {
    "streamer": dict(label="Streamer", desc="Yellow 1-3 words, pop (GTA-clip style)",
                     font="Arial Black", size=88, char_w=0.80, text=_rgb("FFE135"), active=_rgb("FFE135"),
                     outline=BLACK, border=7, shadow=3, back=_rgb("000000", 0x50),
                     mode="chunk", max_words=3, upper=True, pop=116),
    "hormozi": dict(label="Hormozi", desc="White words, yellow active word, reveal",
                    font="Arial Black", size=84, char_w=0.80, text=WHITE, active=_rgb("FFE500"),
                    outline=BLACK, border=6, shadow=3, back=_rgb("000000", 0x50),
                    mode="highlight", reveal=True, max_words=4, upper=True, pop=110),
    "beast": dict(label="Beast", desc="One huge word at a time, colour cycling",
                  font="Impact", size=140, char_w=0.56, text=WHITE,
                  palette=[_rgb("FFE500"), _rgb("3CFF4A"), _rgb("FF3B3B"), _rgb("2DE1FC"), WHITE],
                  outline=BLACK, border=9, shadow=5, back=_rgb("000000", 0x30),
                  mode="single", upper=True, pop=112, tilt=True),
    "neon": dict(label="Neon", desc="Glowing lime outline, electric pop",
                 font="Segoe UI Black", size=84, char_w=0.74, text=WHITE, active=_rgb("A3FF12"),
                 outline=_rgb("4BC800"), border=4, shadow=0, back=BLACK, blur=6,
                 mode="highlight", reveal=False, max_words=3, upper=True, pop=112),
    "boxed": dict(label="Boxed", desc="White text on black box, yellow active",
                  font="Arial Black", size=70, char_w=0.80, text=WHITE, active=_rgb("FFE500"),
                  outline=_rgb("000000", 0x20), border=14, shadow=0, back=BLACK, border_style=3,
                  mode="highlight", reveal=False, max_words=3, upper=True, pop=100),
    "karaoke": dict(label="Karaoke", desc="Words fill orange as they're spoken",
                    font="Arial Black", size=84, char_w=0.80, text=WHITE, active=_rgb("FFB300"),
                    outline=BLACK, border=6, shadow=3, back=_rgb("000000", 0x50),
                    mode="karaoke", max_words=3, upper=True),
    "fire": dict(label="Fire", desc="Gold Impact text, red outline, white pop",
                 font="Impact", size=112, char_w=0.56, text=_rgb("FFC300"), active=WHITE,
                 outline=_rgb("D7141A"), border=6, shadow=4, back=BLACK,
                 mode="chunk", max_words=2, upper=True, pop=120),
    "meme": dict(label="Meme", desc="Comic font, 3D shadow, wobble",
                 font="Comic Sans MS", size=86, char_w=0.68, text=WHITE, active=_rgb("FFE500"),
                 outline=BLACK, border=8, shadow=6, back=BLACK,
                 mode="highlight", reveal=True, max_words=3, upper=True, pop=115, wobble=True),
    "clean": dict(label="Clean", desc="Minimal white, soft shadow",
                  font="Segoe UI", size=76, char_w=0.58, text=WHITE, active=_rgb("FFF3A0"),
                  outline=BLACK, border=0, shadow=3, back=_rgb("000000", 0x70),
                  mode="highlight", reveal=False, max_words=4, upper=False, pop=104),
}
STYLE_ALIASES = {"lime": "neon", "pill": "boxed"}


def resolve_style(name: Optional[str]) -> str:
    name = (name or config.DEFAULT_CAPTION_STYLE).lower()
    name = STYLE_ALIASES.get(name, name)
    return name if name in CAPTION_STYLES else "streamer"


def _clean_title(title: str) -> str:
    """Strip emoji/symbols (libass can't draw colour emoji) and tidy whitespace."""
    import unicodedata
    out = []
    for c in title or "":
        cp = ord(c)
        if unicodedata.category(c) in ("So", "Cs", "Co") or cp >= 0x1F000 or 0xFE00 <= cp <= 0xFE0F or c == "\u200d":
            continue
        out.append(c)
    text = re.sub(r"\s+", " ", "".join(out)).strip(" -|:")
    if len(text) > 60:  # at most ~2 lines in the label
        text = text[:60].rsplit(" ", 1)[0]
    return _escape_ass_text(text)


async def generate_captions(
    all_words: List[WordTimestamp],
    clip_start: float,
    clip_end: float,
    output_path: Path,
    layout_type: str = "split_cam",
    preset: str = "streamer",
    title: Optional[str] = None,
    include_words: bool = True,
    font: Optional[str] = None,
) -> Path:
    """Write an ASS subtitle file with animated word captions (in the chosen style)
    and an optional burned-in title label."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    style_name = resolve_style(preset)
    st = dict(CAPTION_STYLES[style_name])
    font = font or config.CAPTION_FONT_OVERRIDE
    if font:  # user-picked font replaces the style's font
        st["font"] = font
        st["char_w"] = config.CAPTION_FONT_WIDTHS.get(font, 0.72)
    W, H = config.OUTPUT_WIDTH, config.OUTPUT_HEIGHT
    clip_dur = max(0.1, clip_end - clip_start)

    # 1. Words inside the clip, relative timestamps
    raw_clip_words: List[WordTimestamp] = []
    for w in (all_words if include_words else []):
        if w.end >= clip_start and w.start <= clip_end:
            rel_start = max(0.0, round(w.start - clip_start, 2))
            rel_end = max(rel_start + 0.10, round(min(clip_dur, w.end - clip_start), 2))
            if w.word.strip():
                raw_clip_words.append(WordTimestamp(word=w.word.strip(), start=rel_start, end=rel_end,
                                                    confidence=w.confidence))
    clean_words = _merge_continuation_words(raw_clip_words)

    # 2. Geometry
    scale = config.CAPTION_SIZE_SCALE
    size = int(round(st["size"] * scale))
    border = round(st["border"] * (scale if st.get("border_style", 1) == 1 else 1), 1)
    split = layout_type == "split_cam"
    cy = int(H * (config.CAPTION_Y_SPLIT if split else config.CAPTION_Y_DEFAULT))
    avail_w = W - 120
    pop = st.get("pop", 100)

    def est_width(words: List[str], fs: int) -> float:
        chars = sum(len(x) for x in words) + max(0, len(words) - 1)
        return chars * fs * st["char_w"] * max(pop, 100) / 100.0

    max_chars = max(6, int(avail_w / (size * st["char_w"] * max(pop, 100) / 100.0)))
    max_words = 1 if st["mode"] == "single" else st.get("max_words", 3)

    def fmt(word: str) -> str:
        t = _escape_ass_text(word)
        return t.upper() if st.get("upper") else t

    # karaoke: PrimaryColour = filled (active), SecondaryColour = not yet sung (text)
    if st["mode"] == "karaoke":
        primary, secondary = st["active"], st["text"]
    else:
        primary, secondary = st["text"], st.get("active", st["text"])

    title_size = int(round(54 * scale))
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{st['font']},{size},{primary},{secondary},{st['outline']},{st['back']},1,0,0,0,100,100,0,0,{st.get('border_style', 1)},{border},{st['shadow']},5,60,60,0,1
Style: Title,Arial Black,{title_size},{WHITE},{WHITE},{_rgb('000000', 0x10)},{_rgb('000000', 0x10)},1,0,0,0,100,100,0,0,3,14,0,2,90,90,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines: List[str] = []

    # 3. Title label (black box, white uppercase), like streamer clip channels
    clean_title = _clean_title(title) if title else ""  # caller decides whether to pass a title
    if clean_title:
        if split:
            from .reframe import split_cam_height
            pos = f"\\an2\\pos({W // 2},{split_cam_height() - 30})"
        else:
            pos = f"\\an8\\pos({W // 2},{int(H * 0.12)})"
        tfn = _font_override(clean_title, int(title_size * 1.1))
        lines.append(f"Dialogue: 1,{_ass_time(0)},{_ass_time(clip_dur)},Title,,0,0,0,,"
                     f"{{{pos}\\q0\\fad(250,0){tfn}}}{clean_title.upper()}")

    # 4. Word captions
    blocks = _collect_word_blocks(clean_words, max_chars=max_chars, max_duration=1.3)
    # enforce max words per block
    split_blocks: List[List[WordTimestamp]] = []
    for b in blocks:
        for k in range(0, len(b), max_words):
            split_blocks.append(b[k:k + max_words])
    blocks = [b for b in split_blocks if b]

    blur = f"\\blur{st['blur']}" if st.get("blur") else ""
    palette = st.get("palette") or []
    word_counter = 0

    for b_idx, block in enumerate(blocks):
        texts = [fmt(w.word) for w in block]
        fs = size
        if est_width(texts, size) > avail_w:  # shrink this line so it never leaves the frame
            fs = max(int(size * 0.55), int(size * avail_w / est_width(texts, size)))
        line_tags = (f"\\fs{fs}" if fs != size else "") + blur
        reset = "{\\rDefault" + line_tags + "}"
        lead = f"{{\\an5\\pos({W // 2},{cy}){line_tags}}}"
        next_start = blocks[b_idx + 1][0].start if b_idx + 1 < len(blocks) else clip_dur

        def word_end(i: int) -> float:
            e = block[i + 1].start if i < len(block) - 1 else min(block[-1].end + 0.25, next_start)
            e = min(e, block[i].end + 0.6, next_start if i == len(block) - 1 else e)
            start = block[0].start if i == 0 else block[i].start
            return e if e > start else round(start + 0.12, 2)

        if st["mode"] == "karaoke":
            parts = []
            for i, w in enumerate(block):
                nxt = block[i + 1].start if i < len(block) - 1 else w.end
                dur_cs = max(5, int(round((nxt - w.start) * 100)))
                fn = _font_override(texts[i], int(fs * 1.12))
                parts.append(f"{{\\kf{dur_cs}{fn}}}{texts[i]}" + (reset if fn else ""))
            ev_s, ev_e = block[0].start, max(block[0].start + 0.2, min(block[-1].end + 0.3, next_start))
            lines.append(f"Dialogue: 0,{_ass_time(ev_s)},{_ass_time(ev_e)},Default,,0,0,0,,{lead}{' '.join(parts)}")
            continue

        for i, w in enumerate(block):
            ev_s = block[0].start if i == 0 else w.start
            ev_e = word_end(i)
            if st["mode"] == "single":
                color = palette[word_counter % len(palette)] if palette else st["text"]
                tilt = f"\\frz{(-4 if word_counter % 2 else 4)}" if st.get("tilt") else ""
                fn = _font_override(texts[i], int(fs * 1.12))
                body = (f"{{\\c{color}{tilt}{fn}\\fscx70\\fscy70\\t(0,90,\\fscx{pop}\\fscy{pop})"
                        f"\\t(90,170,\\fscx100\\fscy100)}}{texts[i]}")
                lines.append(f"Dialogue: 0,{_ass_time(ev_s)},{_ass_time(max(ev_e, ev_s + 0.25))},Default,,0,0,0,,{lead}{body}")
                word_counter += 1
                continue

            parts = []
            for j, other in enumerate(block):
                fn = _font_override(texts[j], int(fs * 1.12))
                if j == i:
                    color = f"\\c{st['active']}" if st.get("active") and st["active"] != st["text"] else ""
                    wob = f"\\frz{(-3 if i % 2 else 3)}" if st.get("wobble") else ""
                    anim = ""
                    if pop != 100:
                        anim = (f"\\fscx92\\fscy92\\t(0,100,\\fscx{pop}\\fscy{pop})"
                                f"\\t(100,180,\\fscx{100 + (pop - 100) // 2}\\fscy{100 + (pop - 100) // 2})")
                    parts.append(f"{{{fn}{color}{wob}{anim}}}{texts[j]}{reset}")
                elif st.get("reveal") and j > i:
                    parts.append(f"{{{fn}\\alpha&HFF&}}{texts[j]}{reset}")
                else:
                    parts.append(f"{{{fn}}}{texts[j]}{reset}" if fn else texts[j])
            lines.append(f"Dialogue: 0,{_ass_time(ev_s)},{_ass_time(ev_e)},Default,,0,0,0,,{lead}{' '.join(parts)}")

    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(header + "\n".join(lines) + "\n")
    logger.info(f"Captions: style={style_name}, layout={layout_type}, {len(lines)} events, title={'yes' if clean_title else 'no'}")
    return output_path
