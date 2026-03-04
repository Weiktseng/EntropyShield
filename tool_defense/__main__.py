"""
CLI entry point: python -m tool_defense [OPTIONS]

Scan Claude Code conversation logs for sensitive information leaks.
Part of the EntropyShield AI security toolkit.

Usage:
    python -m tool_defense                          # scan ~/.claude/
    python -m tool_defense ~/.claude/ -s CRITICAL   # only CRITICAL
    python -m tool_defense -c "API Keys & Tokens"   # only API keys
    python -m tool_defense --list-patterns          # list all rules
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .scanner import scan_path
from .patterns import PatternRegistry, Severity, Category
from .reporter import generate_report, print_summary, ReportFormat


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tool_defense",
        description="Scan Claude Code logs for sensitive information leaks.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to scan (default: ~/.claude/)",
    )
    parser.add_argument(
        "-o", "--output-dir",
        default=None,
        help="Output directory for reports (default: tool_defense/scan_output/)",
    )
    parser.add_argument(
        "-s", "--severity",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=None,
        help="Minimum severity level to report",
    )
    parser.add_argument(
        "-c", "--category",
        choices=[c.value for c in Category],
        default=None,
        help="Only scan for this category",
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json", "both"],
        default="both",
        help="Report format (default: both)",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Suppress terminal summary output",
    )
    parser.add_argument(
        "--list-patterns",
        action="store_true",
        help="List all detection patterns and exit",
    )

    args = parser.parse_args()

    # Handle --list-patterns
    if args.list_patterns:
        registry = PatternRegistry()
        print("\n  Detection Patterns:")
        print("  " + "-" * 60)
        for p in registry.get_patterns():
            print(f"  [{p.severity.value:8s}] {p.name:30s}  {p.description}")
        print()
        return 0

    # Determine scan path
    scan_root = Path(args.path).expanduser() if args.path else None

    # Determine severity filter
    severity_filter = Severity[args.severity] if args.severity else None

    # Determine category filter
    category_filter = None
    if args.category:
        for cat in Category:
            if cat.value == args.category:
                category_filter = cat
                break

    # Run scan
    print("\n  Scanning Claude Code logs for sensitive data...")
    result = scan_path(
        scan_root=scan_root,
        severity_filter=severity_filter,
        category_filter=category_filter,
    )

    # Generate reports
    formats: list[ReportFormat] = []
    if args.format in ("text", "both"):
        formats.append(ReportFormat.TEXT)
    if args.format in ("json", "both"):
        formats.append(ReportFormat.JSON)

    output_dir = Path(args.output_dir) if args.output_dir else None
    report_paths = generate_report(result, output_dir=output_dir, formats=formats)

    # Print summary
    if not args.no_summary:
        print_summary(result)
        print("  Reports saved:")
        for fmt, path in report_paths.items():
            print(f"    {fmt.value:5s} → {path}")
        print()

    # Exit code: 1 if CRITICAL findings
    critical_count = len(result.findings_by_severity().get(Severity.CRITICAL, []))
    return 1 if critical_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
