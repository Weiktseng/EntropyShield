"""
Core scanning engine for Claude Code conversation log security analysis.

Parses JSONL conversation logs, extracts text fields from nested JSON
structures, and matches against the pattern registry to detect sensitive
information leaks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .patterns import Category, PatternRegistry, Severity, SensitivePattern


class FileType(Enum):
    JSONL_SESSION = "jsonl_session"
    JSONL_SUBAGENT = "jsonl_subagent"
    MARKDOWN_MEMORY = "markdown_memory"
    TEXT_TOOL_RESULT = "text_tool_result"
    JSONL_HISTORY = "jsonl_history"


@dataclass
class Finding:
    """A single sensitive data finding."""

    pattern: SensitivePattern
    matched_text: str
    redacted_text: str
    file_path: str
    file_type: FileType
    line_number: int
    json_field_path: str
    context_snippet: str
    session_id: str = ""
    timestamp: str = ""

    def __repr__(self) -> str:
        return (
            f"Finding({self.pattern.name}, {self.redacted_text!r}, "
            f"line={self.line_number}, field={self.json_field_path})"
        )


@dataclass
class ScanResult:
    """Aggregated results of a full scan."""

    scan_path: str = ""
    scan_timestamp: str = ""
    total_files_scanned: int = 0
    total_lines_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        result: dict[Severity, list[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.pattern.severity, []).append(f)
        return result

    def findings_by_category(self) -> dict[Category, list[Finding]]:
        result: dict[Category, list[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.pattern.category, []).append(f)
        return result

    def findings_by_file(self) -> dict[str, list[Finding]]:
        result: dict[str, list[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.file_path, []).append(f)
        return result


def redact_value(value: str, keep_prefix: int = 4, keep_suffix: int = 3) -> str:
    """
    Redact a sensitive value for safe display.

    >>> redact_value("sk-proj-abc123xyz789")
    'sk-p****789'
    >>> redact_value("short")
    'shor****'
    """
    if len(value) <= keep_prefix + keep_suffix + 4:
        return value[:keep_prefix] + "****"
    return value[:keep_prefix] + "****" + value[-keep_suffix:]


def _make_redacted_context(
    text: str, match_start: int, match_end: int, window: int = 50
) -> str:
    """Extract surrounding context with the match replaced by [REDACTED]."""
    start = max(0, match_start - window)
    end = min(len(text), match_end + window)
    prefix = text[start:match_start].replace("\n", " ")
    suffix = text[match_end:end].replace("\n", " ")
    leader = "..." if start > 0 else ""
    trailer = "..." if end < len(text) else ""
    return f"{leader}{prefix}[REDACTED]{suffix}{trailer}"


def _luhn_check(number_str: str) -> bool:
    """Validate a credit card number using the Luhn algorithm."""
    digits = [int(d) for d in number_str if d.isdigit()]
    if len(digits) != 16:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def scan_text(
    text: str,
    registry: PatternRegistry,
    *,
    file_path: str = "",
    file_type: FileType = FileType.JSONL_SESSION,
    line_number: int = 0,
    json_field_path: str = "",
    session_id: str = "",
    timestamp: str = "",
) -> list[Finding]:
    """Scan a text string against all patterns in the registry."""
    findings: list[Finding] = []
    for pattern in registry.get_patterns():
        for match in pattern.regex.finditer(text):
            matched = match.group(0)

            if registry.is_false_positive(pattern, matched):
                continue

            # Credit card: additional Luhn validation
            if pattern.name == "credit_card" and not _luhn_check(matched):
                continue

            findings.append(Finding(
                pattern=pattern,
                matched_text=matched,
                redacted_text=redact_value(matched),
                file_path=file_path,
                file_type=file_type,
                line_number=line_number,
                json_field_path=json_field_path,
                context_snippet=_make_redacted_context(
                    text, match.start(), match.end()
                ),
                session_id=session_id,
                timestamp=timestamp,
            ))
    return findings


def _extract_text_fields(obj: dict) -> list[tuple[str, str]]:
    """
    Extract all scannable text fields from a JSONL line object.

    Returns list of (json_field_path, text_value) tuples.
    """
    fields: list[tuple[str, str]] = []
    message = obj.get("message")
    if not isinstance(message, dict):
        return fields

    content = message.get("content")

    # User message: content is a plain string
    if isinstance(content, str) and content:
        fields.append(("message.content", content))

    # Assistant message: content is a list of blocks
    elif isinstance(content, list):
        for i, block in enumerate(content):
            if not isinstance(block, dict):
                continue

            block_type = block.get("type", "")

            # Text block
            if block_type == "text" and isinstance(block.get("text"), str):
                fields.append((f"message.content[{i}].text", block["text"]))

            # Thinking block
            elif block_type == "thinking" and isinstance(block.get("thinking"), str):
                fields.append((f"message.content[{i}].thinking", block["thinking"]))

            # Tool use block — scan the input
            elif block_type == "tool_use":
                inp = block.get("input", {})
                if isinstance(inp, dict):
                    # Bash command
                    if isinstance(inp.get("command"), str):
                        fields.append((
                            f"message.content[{i}].input.command",
                            inp["command"],
                        ))
                    # File path
                    if isinstance(inp.get("file_path"), str):
                        fields.append((
                            f"message.content[{i}].input.file_path",
                            inp["file_path"],
                        ))
                    # Generic: stringify all string values in input
                    for key, val in inp.items():
                        if key in ("command", "file_path"):
                            continue
                        if isinstance(val, str) and len(val) > 5:
                            fields.append((
                                f"message.content[{i}].input.{key}",
                                val,
                            ))

            # Tool result block
            elif block_type == "tool_result":
                result_content = block.get("content")
                if isinstance(result_content, str):
                    fields.append((
                        f"message.content[{i}].content",
                        result_content,
                    ))
                elif isinstance(result_content, list):
                    for j, rc in enumerate(result_content):
                        if isinstance(rc, dict) and isinstance(rc.get("text"), str):
                            fields.append((
                                f"message.content[{i}].content[{j}].text",
                                rc["text"],
                            ))

    # Metadata fields
    for meta_key in ("cwd", "gitBranch"):
        val = obj.get(meta_key)
        if isinstance(val, str) and val:
            fields.append((meta_key, val))

    return fields


def scan_jsonl_file(
    file_path: Path,
    registry: PatternRegistry,
    file_type: FileType = FileType.JSONL_SESSION,
) -> tuple[list[Finding], int]:
    """
    Scan a .jsonl file line by line.

    Returns (findings, lines_scanned).
    """
    findings: list[Finding] = []
    lines_scanned = 0
    rel_path = str(file_path)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                lines_scanned += 1
                line = line.strip()
                if not line:
                    continue

                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                session_id = obj.get("sessionId", "")
                timestamp = obj.get("timestamp", "")

                text_fields = _extract_text_fields(obj)
                for field_path, text in text_fields:
                    found = scan_text(
                        text,
                        registry,
                        file_path=rel_path,
                        file_type=file_type,
                        line_number=line_num,
                        json_field_path=field_path,
                        session_id=session_id,
                        timestamp=timestamp,
                    )
                    findings.extend(found)
    except OSError as e:
        return findings, lines_scanned

    return findings, lines_scanned


def scan_text_file(
    file_path: Path,
    registry: PatternRegistry,
    file_type: FileType,
) -> tuple[list[Finding], int]:
    """Scan a plain text file (.md, .txt) line by line."""
    findings: list[Finding] = []
    lines_scanned = 0
    rel_path = str(file_path)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line_num, line in enumerate(f, start=1):
                lines_scanned += 1
                found = scan_text(
                    line,
                    registry,
                    file_path=rel_path,
                    file_type=file_type,
                    line_number=line_num,
                    json_field_path="",
                )
                findings.extend(found)
    except OSError:
        pass

    return findings, lines_scanned


def _discover_files(scan_root: Path) -> list[tuple[Path, FileType]]:
    """
    Walk the Claude Code directory tree and discover all scannable files.
    """
    files: list[tuple[Path, FileType]] = []

    # Global history
    history = scan_root / "history.jsonl"
    if history.is_file():
        files.append((history, FileType.JSONL_HISTORY))

    # Projects directory
    projects_dir = scan_root / "projects"
    if not projects_dir.is_dir():
        return files

    for item in projects_dir.rglob("*"):
        if not item.is_file():
            continue

        rel = item.relative_to(projects_dir)
        parts = rel.parts

        if item.suffix == ".jsonl":
            if "subagents" in parts:
                files.append((item, FileType.JSONL_SUBAGENT))
            else:
                files.append((item, FileType.JSONL_SESSION))
        elif item.suffix == ".md" and "memory" in parts:
            files.append((item, FileType.MARKDOWN_MEMORY))
        elif item.suffix == ".txt" and "tool-results" in parts:
            files.append((item, FileType.TEXT_TOOL_RESULT))

    return files


def scan_path(
    scan_root: Path | None = None,
    registry: PatternRegistry | None = None,
    severity_filter: Severity | None = None,
    category_filter: Category | None = None,
) -> ScanResult:
    """
    Main entry point: scan a directory tree for sensitive data in
    Claude Code conversation logs.

    Args:
        scan_root: Root directory to scan. Defaults to ~/.claude/
        registry: Pattern registry. Uses built-in patterns if None.
        severity_filter: Only report findings at this severity or above.
        category_filter: Only report findings in this category.
    """
    from datetime import datetime, timezone

    if scan_root is None:
        scan_root = Path.home() / ".claude"

    if registry is None:
        registry = PatternRegistry()

    # Apply filters to registry
    if severity_filter or category_filter:
        filtered_registry = PatternRegistry()
        filtered_registry._patterns = registry.get_patterns(
            severity=severity_filter, category=category_filter
        )
        registry = filtered_registry

    result = ScanResult(
        scan_path=str(scan_root),
        scan_timestamp=datetime.now(timezone.utc).isoformat(),
    )

    if not scan_root.is_dir():
        result.errors.append(f"Scan root does not exist: {scan_root}")
        return result

    files = _discover_files(scan_root)

    for file_path, file_type in files:
        result.total_files_scanned += 1

        if file_type in (
            FileType.JSONL_SESSION,
            FileType.JSONL_SUBAGENT,
            FileType.JSONL_HISTORY,
        ):
            findings, lines = scan_jsonl_file(file_path, registry, file_type)
        else:
            findings, lines = scan_text_file(file_path, registry, file_type)

        result.total_lines_scanned += lines
        result.findings.extend(findings)

    return result
