"""
EntropyShield — Deterministic Prompt Injection Defense via Semantic Fragmentation
DeSyntax: Destroy command syntax, preserve semantic density.

Author: Weiktseng
License: MIT
"""

__version__ = "0.1.0"

from .fragmenter import fragment, fragment_line, fragment_text
from .adaptive_reader import AdaptiveReader
from .detector import detect_leak

__all__ = [
    "fragment",
    "fragment_line",
    "fragment_text",
    "AdaptiveReader",
    "detect_leak",
]
