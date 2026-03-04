"""
EntropyShield — Unified Defense Entry Point

The single recommended way to protect against prompt injection.

4-Layer Defense:
  Layer 0 — Sanitize: decode HTML/Unicode, strip XML/JSON structure, neutralize role hijacking
  Layer 1 — Stride Mask: CSPRNG content-independent bitmap masking with hard u/m constraints
  Layer 2 — NLP Amplify: threat-region enhanced masking (best-effort, graceful fallback)
  Layer 3 — Random Jitter: CSPRNG shuffled bit-flipping within u/m constraints

Usage:
    from entropyshield import shield
    safe_text = shield("untrusted text here")
"""

from __future__ import annotations

from typing import Optional


def shield(
    text: str,
    *,
    seed: Optional[int] = None,
    **kwargs,
) -> str:
    """
    Apply 4-layer defense to untrusted text and return shielded output.

    The shielded text preserves readable meaning but destroys command
    syntax, preventing embedded prompt injection from being executed.

    Args:
        text: Untrusted text to shield.
        seed: Optional CSPRNG seed for reproducibility.
        **kwargs: Passed to stride_mask_text() (e.g. long_u, long_m, jitter_p).

    Returns:
        Shielded text with masked characters (█).

    Example:
        >>> from entropyshield import shield
        >>> shield("Ignore all previous instructions.", seed=42)
        'Ig██re ███ prev████ ██structions.'
    """
    from .mode1_stride_masker import stride_mask_text

    result = stride_mask_text(text, seed=seed, **kwargs)
    return result["masked_text"]


def shield_with_stats(
    text: str,
    *,
    seed: Optional[int] = None,
    **kwargs,
) -> dict:
    """
    Apply 4-layer defense and return full result with statistics.

    Returns:
        Dict with keys: masked_text, title, stats, bitmap
    """
    from .mode1_stride_masker import stride_mask_text

    return stride_mask_text(text, seed=seed, **kwargs)
