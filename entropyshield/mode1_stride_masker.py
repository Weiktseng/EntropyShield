"""
EntropyShield Mode 1 v2 — Stride Masking (default defense)

Architecture:
  Layer 0: Sanitize (encoding evasion, XML, role hijacking)
  Layer 1: Stride Mask — content-independent hard u/m bitmap
  Layer 2: NLP Amplifier — threat regions get extra masking
  Layer 3: Random Jitter — truly random flips within u/m constraints

Two tiers by text length:
  Short text (≤ LONG_THRESHOLD chars): character-level stride
  Long  text (>  LONG_THRESHOLD chars): token-level stride + NLP + jitter

Texts ≤ SKIP_LEN chars (atomic values) pass through untouched.
"""

import random
import re
from typing import Optional

from .entropy_harvester import make_seed as _make_seed
from .fragmenter import sanitize_delimiters

# ── Constants ──

MASK_CHAR = "\u2588"  # █

_CJK_RE = re.compile(
    r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
    r"\u3040-\u309f\u30a0-\u30ff"  # hiragana, katakana
    r"\uac00-\ud7af]"              # hangul
)

# ── Defaults (all adjustable) ──

SKIP_LEN = 3            # ≤ 3 chars: atomic value, pass through
LONG_THRESHOLD = 30     # > 30 chars → token-level; ≤ 30 → char-level

# Short text (char-level)
SHORT_U = 4             # max consecutive visible chars
SHORT_M = 3             # max consecutive masked chars

# Long text (token-level)
LONG_U = 3              # max consecutive visible tokens
LONG_M = 2              # max consecutive masked tokens

JITTER_P = 0.3          # flip probability per unit in Layer 3


def _get_rng(seed: Optional[int] = None) -> random.Random:
    if seed is None:
        seed = _make_seed()
    return random.Random(seed)


# ═══════════════════════════════════════════
#  Tokenizer — word-level Latin, char-level CJK
# ═══════════════════════════════════════════

def tokenize(text: str) -> list[dict]:
    """Split text into tokens preserving original positions.

    Latin/mixed words → one token per space-separated word.
    CJK characters    → one token per character.
    """
    tokens: list[dict] = []
    i = 0
    n = len(text)

    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if _CJK_RE.match(text[i]):
            tokens.append({"text": text[i], "start": i, "end": i + 1})
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and not _CJK_RE.match(text[j]):
                j += 1
            tokens.append({"text": text[i:j], "start": i, "end": j})
            i = j

    return tokens


def render_tokens(text: str, tokens: list[dict], bitmap: list[bool]) -> str:
    """Apply token-level bitmap: masked tokens → █ chars."""
    chars = list(text)
    for tok, visible in zip(tokens, bitmap):
        if not visible:
            for k in range(tok["start"], tok["end"]):
                if not chars[k].isspace():
                    chars[k] = MASK_CHAR
    return "".join(chars)


def render_chars(text: str, bitmap: list[bool]) -> str:
    """Apply char-level bitmap: masked chars → █."""
    result = []
    bi = 0
    for ch in text:
        if ch.isspace():
            result.append(ch)
        else:
            if bi < len(bitmap) and not bitmap[bi]:
                result.append(MASK_CHAR)
            else:
                result.append(ch)
            bi += 1
    return "".join(result)


# ═══════════════════════════════════════════
#  Core — Stride Bitmap Generator
# ═══════════════════════════════════════════

def gen_stride_bitmap(n: int, u: int, m: int, rng: random.Random) -> list[bool]:
    """Generate masking bitmap with hard u/m guarantees.

    Alternates random visible runs [1..u] and masked runs [1..m].
    Pattern depends only on CSPRNG seed, NOT on content.
    """
    bitmap: list[bool] = []
    while len(bitmap) < n:
        show = rng.randint(1, u)
        bitmap.extend([True] * min(show, n - len(bitmap)))
        if len(bitmap) >= n:
            break
        hide = rng.randint(1, m)
        bitmap.extend([False] * min(hide, n - len(bitmap)))
    return bitmap[:n]


# ═══════════════════════════════════════════
#  Layer 2 — NLP Amplifier (best-effort)
# ═══════════════════════════════════════════

def layer2_nlp_amplify(
    tokens: list[dict],
    bitmap: list[bool],
    u: int,
    m: int,
) -> list[bool]:
    """Amplify masking in NLP-detected threat regions.

    Can only flip True → False. Must respect m constraint.
    If NLP unavailable, returns bitmap unchanged (Layer 1 protects).
    """
    try:
        from .nlp_signals import detect_threat_spans
        threat_spans = detect_threat_spans(tokens)
    except (ImportError, ModuleNotFoundError):
        return list(bitmap)

    bitmap = list(bitmap)
    for start, end in threat_spans:
        for i in range(start, min(end, len(bitmap))):
            if bitmap[i]:
                bitmap[i] = False
                if not _check_constraints(bitmap, i, u, m):
                    bitmap[i] = True
    return bitmap


# ═══════════════════════════════════════════
#  Layer 3 — Random Jitter
# ═══════════════════════════════════════════

def layer3_jitter(
    bitmap: list[bool],
    u: int,
    m: int,
    rng: random.Random,
    p: float = JITTER_P,
) -> list[bool]:
    """Randomly flip visible↔masked without violating u/m constraints.

    Shuffled visit order + per-unit coin flip = truly unpredictable.
    """
    bitmap = list(bitmap)
    n = len(bitmap)

    indices = list(range(n))
    rng.shuffle(indices)

    for i in indices:
        if rng.random() >= p:
            continue
        original = bitmap[i]
        bitmap[i] = not original
        if not _check_constraints(bitmap, i, u, m):
            bitmap[i] = original

    return bitmap


def _check_constraints(bitmap: list[bool], pos: int, u: int, m: int) -> bool:
    """Check if u/m constraints hold around position pos."""
    n = len(bitmap)
    val = bitmap[pos]
    max_run = u if val else m
    run = 1
    j = pos - 1
    while j >= 0 and bitmap[j] == val:
        run += 1
        j -= 1
    j = pos + 1
    while j < n and bitmap[j] == val:
        run += 1
        j += 1
    return run <= max_run


# ═══════════════════════════════════════════
#  Language Detection
# ═══════════════════════════════════════════

def detect_lang(text: str) -> str:
    """Detect dominant script: 'cjk', 'latin', or 'mixed'."""
    cjk = sum(1 for c in text if _CJK_RE.match(c))
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    total = cjk + latin
    if total == 0:
        return "latin"
    if cjk / total > 0.6:
        return "cjk"
    if latin / total > 0.6:
        return "latin"
    return "mixed"


def adaptive_params(
    text: str, u: int, m: int, short_u: int, short_m: int, is_short: bool,
) -> tuple[int, int]:
    """Adjust u/m for CJK/mixed text."""
    lang = detect_lang(text)
    if is_short:
        base_u, base_m = short_u, short_m
    else:
        base_u, base_m = u, m

    if lang in ("cjk", "mixed"):
        return max(2, base_u - 1), max(1, base_m - 1)
    return base_u, base_m


# ═══════════════════════════════════════════
#  Title — category-only, never echo attack text
# ═══════════════════════════════════════════

def build_title(stats: dict) -> str:
    """Safe title: only categories + statistics, never echo content."""
    if stats.get("skipped"):
        return ""

    ratio_pct = stats["ratio"] * 100
    mode = stats.get("mode", "stride")
    parts = [f"{ratio_pct:.0f}% visible ({stats['visible']}/{stats['total']})"]

    if stats.get("nlp_regions", 0) > 0:
        parts.append(f"{stats['nlp_regions']} regions amplified")

    return f"\u26a0 {mode}-masked: {', '.join(parts)}\n\u2500\u2500\u2500\u2500\n"


# ═══════════════════════════════════════════
#  Short Text Pipeline (char-level)
# ═══════════════════════════════════════════

def _mask_short(
    text: str,
    u: int,
    m: int,
    rng: random.Random,
    jitter_p: float,
) -> dict:
    """Char-level stride masking for short text (≤ LONG_THRESHOLD)."""
    # Count non-space chars for bitmap
    non_space = [i for i, ch in enumerate(text) if not ch.isspace()]
    n = len(non_space)

    if n == 0:
        return _skip_result(text)

    # Layer 1: char-level stride
    bitmap = gen_stride_bitmap(n, u, m, rng)

    # Layer 3: jitter (no NLP for short text — too few tokens)
    bitmap = layer3_jitter(bitmap, u, m, rng, p=jitter_p)

    # Render
    masked_text = render_chars(text, bitmap)

    visible = sum(1 for b in bitmap if b)
    return {
        "masked_text": masked_text,
        "title": build_title({
            "total": n, "visible": visible,
            "ratio": visible / n, "mode": "char-stride",
        }),
        "stats": {
            "total": n, "visible": visible, "masked": n - visible,
            "ratio": visible / n, "mode": "char-stride",
            "u": u, "m": m, "skipped": False,
        },
        "bitmap": bitmap,
    }


# ═══════════════════════════════════════════
#  Long Text Pipeline (token-level)
# ═══════════════════════════════════════════

def _mask_long(
    text: str,
    u: int,
    m: int,
    rng: random.Random,
    jitter_p: float,
) -> dict:
    """Token-level stride masking for long text (> LONG_THRESHOLD)."""
    tokens = tokenize(text)
    n = len(tokens)

    if n == 0:
        return _skip_result(text)

    # Layer 1: token-level stride
    bitmap = gen_stride_bitmap(n, u, m, rng)

    # Layer 2: NLP amplifier
    bitmap = layer2_nlp_amplify(tokens, bitmap, u, m)

    # Layer 3: jitter
    bitmap = layer3_jitter(bitmap, u, m, rng, p=jitter_p)

    # Render
    masked_text = render_tokens(text, tokens, bitmap)

    visible = sum(1 for b in bitmap if b)
    lang = detect_lang(text)
    return {
        "masked_text": masked_text,
        "title": build_title({
            "total": n, "visible": visible,
            "ratio": visible / n, "mode": "token-stride",
            "lang": lang,
        }),
        "stats": {
            "total": n, "visible": visible, "masked": n - visible,
            "ratio": visible / n, "mode": "token-stride",
            "lang": lang, "u": u, "m": m, "skipped": False,
        },
        "bitmap": bitmap,
    }


def _skip_result(text: str) -> dict:
    return {
        "masked_text": text,
        "title": "",
        "stats": {"total": len(text), "visible": len(text),
                  "masked": 0, "ratio": 1.0, "skipped": True},
        "bitmap": None,
    }


# ═══════════════════════════════════════════
#  Main Entry Point
# ═══════════════════════════════════════════

def stride_mask_text(
    text: str,
    *,
    long_u: int = LONG_U,
    long_m: int = LONG_M,
    short_u: int = SHORT_U,
    short_m: int = SHORT_M,
    skip_len: int = SKIP_LEN,
    long_threshold: int = LONG_THRESHOLD,
    jitter_p: float = JITTER_P,
    seed: Optional[int] = None,
    adapt_lang: bool = True,
) -> dict:
    """EntropyShield Mode 1 v2 — default defense pipeline.

    Handles all text lengths:
      ≤ skip_len chars:       pass through (atomic values: "OK", "42")
      skip_len < len ≤ long:  char-level stride (SHORT_U/SHORT_M)
      len > long:             token-level stride + NLP + jitter (LONG_U/LONG_M)

    Args:
        text:            Input text (potentially malicious).
        long_u/long_m:   Token-level stride params for long text.
        short_u/short_m: Char-level stride params for short text.
        skip_len:        Texts ≤ this pass through entirely.
        long_threshold:  Boundary between short/long pipelines.
        jitter_p:        Random flip probability in Layer 3.
        seed:            CSPRNG seed (None = auto).
        adapt_lang:      Auto-adjust params for CJK/mixed.

    Returns dict:
        masked_text, title, stats, bitmap
    """
    # Atomic values → pass through
    if len(text) <= skip_len:
        return _skip_result(text)

    # Layer 0: Sanitize
    text = sanitize_delimiters(text)

    rng = _get_rng(seed)
    is_short = len(text) <= long_threshold

    # Language-adaptive params
    if adapt_lang:
        if is_short:
            u, m = adaptive_params(text, long_u, long_m, short_u, short_m, True)
        else:
            u, m = adaptive_params(text, long_u, long_m, short_u, short_m, False)
    else:
        u, m = (short_u, short_m) if is_short else (long_u, long_m)

    if is_short:
        return _mask_short(text, u, m, rng, jitter_p)
    else:
        return _mask_long(text, u, m, rng, jitter_p)
