"""
Report generation for scan results.

Generates human-readable (text) and machine-readable (JSON) reports
with all sensitive values redacted. Output files are written with
restricted permissions (chmod 600).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from .patterns import Category, Severity
from .scanner import Finding, ScanResult


class ReportFormat(Enum):
    TEXT = "text"
    JSON = "json"


_SEVERITY_ORDER = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]


def _write_secure_file(path: Path, content: str) -> None:
    """
    Write content to a file with restricted permissions (chmod 600).

    Uses os.open with explicit mode flags to create the file atomically
    with correct permissions, avoiding TOCTOU race conditions.
    """
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def _default_output_dir() -> Path:
    """Return the default output directory for scan reports."""
    return Path(__file__).parent / "scan_output"


def _generate_text_report(result: ScanResult) -> str:
    """Generate human-readable text report with redacted values."""
    lines: list[str] = []

    lines.append("=" * 64)
    lines.append("  EntropyShield — Claude Code Log Security Scan Report")
    lines.append(f"  Generated: {result.scan_timestamp}")
    lines.append(f"  Scan path: {result.scan_path}")
    lines.append("=" * 64)
    lines.append("")

    # Summary
    by_sev = result.findings_by_severity()
    by_cat = result.findings_by_category()

    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Files scanned:   {result.total_files_scanned:,}")
    lines.append(f"  Lines scanned:   {result.total_lines_scanned:,}")
    lines.append(f"  Total findings:  {result.finding_count}")
    lines.append("")
    lines.append("  By severity:")
    for sev in _SEVERITY_ORDER:
        count = len(by_sev.get(sev, []))
        if count > 0:
            lines.append(f"    {sev.value:10s} {count}")
    lines.append("")
    lines.append("  By category:")
    for cat in Category:
        count = len(by_cat.get(cat, []))
        if count > 0:
            lines.append(f"    {cat.value:40s} {count}")
    lines.append("")

    # Findings by severity
    if result.findings:
        lines.append("=" * 64)
        lines.append("FINDINGS BY SEVERITY")
        lines.append("=" * 64)

        idx = 0
        for sev in _SEVERITY_ORDER:
            sev_findings = by_sev.get(sev, [])
            if not sev_findings:
                continue

            lines.append("")
            lines.append(f"--- {sev.value} ({len(sev_findings)}) ---")
            lines.append("")

            for f in sev_findings:
                idx += 1
                # Shorten file path for readability
                short_path = f.file_path
                if len(short_path) > 60:
                    short_path = "..." + short_path[-57:]

                lines.append(f"[{idx}] {f.pattern.name}")
                lines.append(f"    File:      {short_path}")
                lines.append(f"    Type:      {f.file_type.value}")
                lines.append(f"    Line:      {f.line_number:,}")
                if f.json_field_path:
                    lines.append(f"    Field:     {f.json_field_path}")
                if f.session_id:
                    lines.append(f"    Session:   {f.session_id}")
                if f.timestamp:
                    lines.append(f"    Timestamp: {f.timestamp}")
                lines.append(f"    Matched:   {f.redacted_text}")
                lines.append(f"    Context:   {f.context_snippet}")
                lines.append(f"    Pattern:   {f.pattern.description}")
                lines.append("")

        # Per-file breakdown
        by_file = result.findings_by_file()
        lines.append("=" * 64)
        lines.append("PER-FILE BREAKDOWN")
        lines.append("=" * 64)
        for fpath, file_findings in sorted(by_file.items()):
            short = fpath if len(fpath) <= 60 else "..." + fpath[-57:]
            lines.append(f"\n  {short} ({len(file_findings)} findings)")
            for f in file_findings:
                lines.append(
                    f"    [{f.pattern.severity.value:8s}] "
                    f"{f.pattern.name} (line {f.line_number})"
                )

    # Errors
    if result.errors:
        lines.append("")
        lines.append("=" * 64)
        lines.append("ERRORS")
        lines.append("=" * 64)
        for err in result.errors:
            lines.append(f"  {err}")

    # Footer
    lines.append("")
    lines.append("=" * 64)
    lines.append("  WARNING: This report contains redacted references to")
    lines.append("  sensitive data. Keep this file secure.")
    lines.append("  Do not commit to version control.")
    lines.append("=" * 64)

    return "\n".join(lines) + "\n"


def _generate_json_report(result: ScanResult) -> str:
    """Generate machine-readable JSON report with redacted values."""
    by_sev = result.findings_by_severity()
    by_cat = result.findings_by_category()

    report = {
        "scan_metadata": {
            "tool": "EntropyShield tool_defense",
            "version": "0.1.0",
            "timestamp": result.scan_timestamp,
            "scan_path": result.scan_path,
        },
        "summary": {
            "files_scanned": result.total_files_scanned,
            "lines_scanned": result.total_lines_scanned,
            "total_findings": result.finding_count,
            "by_severity": {
                sev.value: len(by_sev.get(sev, []))
                for sev in _SEVERITY_ORDER
            },
            "by_category": {
                cat.value: len(by_cat.get(cat, []))
                for cat in Category
            },
        },
        "findings": [
            {
                "id": i + 1,
                "pattern_name": f.pattern.name,
                "severity": f.pattern.severity.value,
                "category": f.pattern.category.value,
                "description": f.pattern.description,
                "file_path": f.file_path,
                "file_type": f.file_type.value,
                "line_number": f.line_number,
                "json_field_path": f.json_field_path,
                "session_id": f.session_id,
                "timestamp": f.timestamp,
                "redacted_match": f.redacted_text,
                "redacted_context": f.context_snippet,
            }
            for i, f in enumerate(result.findings)
        ],
        "errors": result.errors,
    }

    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def generate_report(
    result: ScanResult,
    output_dir: Path | None = None,
    formats: list[ReportFormat] | None = None,
) -> dict[ReportFormat, Path]:
    """
    Generate scan reports in requested formats.

    All output files are created with mode 0o600 (owner read/write only).

    Returns dict mapping format to output file path.
    """
    if output_dir is None:
        output_dir = _default_output_dir()
    if formats is None:
        formats = [ReportFormat.TEXT, ReportFormat.JSON]

    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outputs: dict[ReportFormat, Path] = {}

    if ReportFormat.TEXT in formats:
        path = output_dir / f"scan_{ts}.txt"
        _write_secure_file(path, _generate_text_report(result))
        outputs[ReportFormat.TEXT] = path

    if ReportFormat.JSON in formats:
        path = output_dir / f"scan_{ts}.json"
        _write_secure_file(path, _generate_json_report(result))
        outputs[ReportFormat.JSON] = path

    return outputs


def print_summary(result: ScanResult) -> None:
    """
    Print a brief summary to stdout.

    Shows counts only, never actual sensitive values.
    """
    by_sev = result.findings_by_severity()

    print()
    print("  EntropyShield Log Scanner Results")
    print("  " + "=" * 35)
    print(f"  Files scanned:  {result.total_files_scanned:,}")
    print(f"  Lines scanned:  {result.total_lines_scanned:,}")
    print(f"  Total findings: {result.finding_count}")
    print()

    if result.findings:
        print("  By severity:")
        for sev in _SEVERITY_ORDER:
            count = len(by_sev.get(sev, []))
            if count > 0:
                print(f"    {sev.value:10s} {count}")

        by_cat = result.findings_by_category()
        print()
        print("  By category:")
        for cat in Category:
            count = len(by_cat.get(cat, []))
            if count > 0:
                print(f"    {cat.value:40s} {count}")
        print()

    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for err in result.errors:
            print(f"    {err}")
        print()
