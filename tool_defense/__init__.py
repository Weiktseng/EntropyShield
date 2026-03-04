"""
tool_defense — Claude Code Conversation Log Security Scanner

Scans Claude Code conversation logs (~/.claude/) for sensitive
information leaks: API keys, connection strings, cryptographic
material, PII, and environment variable values.

Part of the EntropyShield AI security toolkit.
"""

__version__ = "0.1.0"

from .scanner import scan_path, ScanResult, Finding
from .patterns import PatternRegistry, SensitivePattern, Severity, Category
from .reporter import generate_report, print_summary, ReportFormat

__all__ = [
    "scan_path",
    "ScanResult",
    "Finding",
    "PatternRegistry",
    "SensitivePattern",
    "Severity",
    "Category",
    "generate_report",
    "print_summary",
    "ReportFormat",
]
