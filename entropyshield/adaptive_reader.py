"""
Adaptive Resolution Reader — Dynamic LOD (Level of Detail) for Text

Inspired by 3D game engine LOD techniques:
  - Far (overview):  Head/Tail + random fragments (low resolution)
  - Near (focus):    Regex-matched sections preserved intact (high resolution)
  - Interactive:     LLM decides whether to EXPAND, DISCARD, or FULL_READ

This enables zero-token filtering: determine document relevance at
minimal cost before spending API tokens on full context.
"""

import random
import re
from dataclasses import dataclass, field
from typing import Optional

from .fragmenter import fragment_text


# Default high-priority section patterns (academic papers)
DEFAULT_HIGH_PRIORITY_PATTERNS = [
    r"(?i)(#+\s*)?(abstract|method|methodology|approach)",
    r"(?i)(#+\s*)?(results?|findings?|evaluation)",
    r"(?i)(#+\s*)?(experiment|implementation|setup)",
    r"(?i)(#+\s*)?(figure|fig\.|table|plot|chart)",
    r"(?i)(#+\s*)?(conclusion|summary|discussion)",
    r"(?i)(#+\s*)?(algorithm|procedure|protocol)",
]


@dataclass
class Section:
    """A classified section of the document."""
    title: str
    content: str
    priority: str  # "high" | "low"
    start_line: int
    end_line: int


@dataclass
class ReadingPlan:
    """Output of the adaptive reader — a multi-resolution view."""
    head: str
    tail: str
    high_res_sections: list[Section] = field(default_factory=list)
    low_res_fragments: list[str] = field(default_factory=list)
    total_chars: int = 0
    preview_chars: int = 0

    @property
    def compression_ratio(self) -> float:
        if self.total_chars == 0:
            return 0.0
        return self.preview_chars / self.total_chars

    def to_prompt(self) -> str:
        """Format the reading plan as a prompt for LLM triage."""
        parts = []
        parts.append(f"[DOCUMENT PREVIEW — {self.total_chars} chars total, "
                      f"showing {self.preview_chars} chars "
                      f"({self.compression_ratio:.0%} compression)]")
        parts.append("")
        parts.append(f"[HEAD]\n{self.head}")
        parts.append("")

        if self.high_res_sections:
            parts.append("[HIGH-RESOLUTION SECTIONS]")
            for sec in self.high_res_sections:
                parts.append(f"  --- {sec.title} (lines {sec.start_line}-{sec.end_line}) ---")
                parts.append(f"  {sec.content}")
                parts.append("")

        if self.low_res_fragments:
            parts.append("[LOW-RESOLUTION FRAGMENTS]")
            for frag in self.low_res_fragments:
                parts.append(f"  {frag}")
            parts.append("")

        parts.append(f"[TAIL]\n{self.tail}")
        parts.append("")
        parts.append("[ACTIONS: EXPAND_SECTION(name) | FULL_READ | DISCARD]")

        return "\n".join(parts)


class AdaptiveReader:
    """
    Multi-resolution document reader.

    Scans a document and produces a ReadingPlan with:
      - Head/Tail preserved intact for global context
      - High-priority sections (matched by regex) preserved at full resolution
      - Low-priority sections fragmented into random samples
    """

    def __init__(
        self,
        high_priority_patterns: Optional[list[str]] = None,
        head_lines: int = 10,
        tail_lines: int = 10,
        fragment_max_len: int = 9,
        low_res_sample_rate: float = 0.3,
    ):
        """
        Args:
            high_priority_patterns: Regex patterns that identify important sections.
            head_lines:            Number of lines to preserve from document start.
            tail_lines:            Number of lines to preserve from document end.
            fragment_max_len:      Max char length for low-res fragments.
            low_res_sample_rate:   Fraction of low-priority lines to sample (0.0-1.0).
        """
        patterns = high_priority_patterns or DEFAULT_HIGH_PRIORITY_PATTERNS
        self.high_priority_re = [re.compile(p) for p in patterns]
        self.head_lines = head_lines
        self.tail_lines = tail_lines
        self.fragment_max_len = fragment_max_len
        self.low_res_sample_rate = low_res_sample_rate

    def _is_high_priority(self, line: str) -> bool:
        return any(p.search(line) for p in self.high_priority_re)

    def _extract_sections(self, lines: list[str]) -> list[Section]:
        """Identify contiguous high-priority sections."""
        sections = []
        in_section = False
        current_title = ""
        current_lines = []
        current_start = 0

        for i, line in enumerate(lines):
            if self._is_high_priority(line):
                if not in_section:
                    in_section = True
                    current_title = line.strip()
                    current_start = i
                    current_lines = [line]
                else:
                    current_lines.append(line)
            else:
                if in_section:
                    # Continue capturing up to 15 lines after header match
                    if len(current_lines) < 20:
                        current_lines.append(line)
                    else:
                        sections.append(Section(
                            title=current_title,
                            content="\n".join(current_lines),
                            priority="high",
                            start_line=current_start,
                            end_line=i,
                        ))
                        in_section = False
                        current_lines = []

        if in_section and current_lines:
            sections.append(Section(
                title=current_title,
                content="\n".join(current_lines),
                priority="high",
                start_line=current_start,
                end_line=len(lines) - 1,
            ))

        return sections

    def read(self, text: str) -> ReadingPlan:
        """
        Produce a multi-resolution ReadingPlan from raw text.

        Args:
            text: The full document text.

        Returns:
            ReadingPlan with head, tail, high-res sections, and low-res fragments.
        """
        lines = text.split("\n")
        total = len(lines)

        # Head and Tail
        head = "\n".join(lines[:self.head_lines])
        tail = "\n".join(lines[max(0, total - self.tail_lines):])

        # High-resolution sections
        middle_lines = lines[self.head_lines:max(0, total - self.tail_lines)]
        high_sections = self._extract_sections(middle_lines)
        high_line_ranges = set()
        for sec in high_sections:
            for i in range(sec.start_line, sec.end_line + 1):
                high_line_ranges.add(i)

        # Low-resolution: sample & fragment remaining lines
        low_lines = [
            (i, line) for i, line in enumerate(middle_lines)
            if i not in high_line_ranges and line.strip()
        ]
        sample_count = max(1, int(len(low_lines) * self.low_res_sample_rate))
        sampled = random.sample(low_lines, min(sample_count, len(low_lines)))
        sampled.sort(key=lambda x: x[0])

        low_fragments = [
            fragment_text(line, self.fragment_max_len)
            for _, line in sampled
        ]

        # Calculate sizes
        preview_chars = len(head) + len(tail)
        preview_chars += sum(len(s.content) for s in high_sections)
        preview_chars += sum(len(f) for f in low_fragments)

        return ReadingPlan(
            head=head,
            tail=tail,
            high_res_sections=high_sections,
            low_res_fragments=low_fragments,
            total_chars=len(text),
            preview_chars=preview_chars,
        )
