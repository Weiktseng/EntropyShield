"""
Core Fragmentation Engine — High-Entropy Fragmentation (HEF)

Destroys syntactic structure of input text while preserving semantic density.
An LLM can reconstruct meaning from fragments but cannot execute commands
because the imperative chain is physically broken.

Two modes:
  1. fragment()       — random positional sampling (for security analysis)
  2. fragment_text()  — sequential line-by-line fragmentation (for reading)
"""

import random
import re
from typing import Optional


def fragment(
    text: str,
    max_len: int = 9,
    seed: Optional[int] = None,
) -> tuple[list[tuple[int, int, str]], str, str]:
    """
    Stochastic Positional Fragmentation.

    Randomly samples fragments from the input text, destroying any
    continuous syntactic structure (imperative verbs + objects + conditions).

    Args:
        text:    Raw input text (potentially malicious).
        max_len: Maximum fragment length in characters (default 9).
                 Must stay below the Instruction Trigger Threshold.
        seed:    Optional random seed for reproducibility.

    Returns:
        (fragments, frag_str, joined)
        - fragments: list of (start, end, text_slice) tuples
        - frag_str:  debug string like [0:4]"igno" [7:12]"revio"
        - joined:    space-joined fragment texts for LLM input
    """
    if seed is not None:
        random.seed(seed)

    n = len(text)
    if n == 0:
        return [], "", ""

    num_frags = random.randint(max(2, n // 10), max(3, n // 4))
    fragments = []

    for _ in range(num_frags):
        start = random.randint(0, n - 1)
        length = random.randint(2, max_len)
        end = min(start + length, n)
        fragments.append((start, end, text[start:end]))

    fragments.sort(key=lambda x: x[0])
    frag_str = " ".join(f'[{s}:{e}]"{t}"' for s, e, t in fragments)
    joined = " ".join(t for _, _, t in fragments)

    return fragments, frag_str, joined


def fragment_line(line: str, max_len: int = 9) -> str:
    """
    Sequential fragmentation of a single line.

    Iterates through the line with random skips (0-3 chars) and
    random slice lengths (2-max_len chars), producing a human-readable
    but syntax-broken output.

    Args:
        line:    A single line of text.
        max_len: Maximum fragment length.

    Returns:
        Fragmented line with fragments joined by " | ".
    """
    n = len(line)
    if n <= 3:
        return line

    fragments = []
    pos = 0

    while pos < n:
        skip = random.randint(0, 3)
        pos += skip
        if pos >= n:
            break
        length = random.randint(2, max_len)
        end = min(pos + length, n)
        fragments.append(line[pos:end])
        pos = end

    return " | ".join(fragments)


def fragment_text(
    text: str,
    max_len: int = 9,
    separator: str = " | ",
) -> str:
    """
    Line-by-line sequential fragmentation.

    Preserves paragraph structure (empty lines) while fragmenting
    each content line. Suitable for reading documents where you want
    to maintain section awareness.

    Args:
        text:      Multi-line input text.
        max_len:   Maximum fragment length per slice.
        separator: String used to join fragments within a line.

    Returns:
        Fragmented text preserving paragraph boundaries.
    """
    lines = text.split("\n")
    result = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        result.append(fragment_line(stripped, max_len))

    return "\n".join(result)


def fragment_with_anchors(
    text: str,
    max_len: int = 9,
    head_chars: int = 80,
    tail_chars: int = 80,
) -> str:
    """
    Head + Tail anchoring with fragmented middle.

    Provides the first and last N characters intact for context,
    while fragmenting everything in between.

    Args:
        text:       Input text.
        max_len:    Max fragment length for the middle section.
        head_chars: Number of leading characters to preserve intact.
        tail_chars: Number of trailing characters to preserve intact.

    Returns:
        "[HEAD] ... [FRAGMENTS] ... [TAIL]" formatted string.
    """
    n = len(text)
    if n <= head_chars + tail_chars:
        return fragment_text(text, max_len)

    head = text[:head_chars]
    tail = text[n - tail_chars:]
    middle = text[head_chars:n - tail_chars]

    fragmented_middle = fragment_text(middle, max_len)

    return (
        f"[HEAD] {head}\n"
        f"[FRAGMENTS] {fragmented_middle}\n"
        f"[TAIL] {tail}"
    )
