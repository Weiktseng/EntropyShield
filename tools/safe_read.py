#!/usr/bin/env python3
"""
safe_read.py — Read untrusted files through EntropyShield.

Always use this instead of direct file reads for:
- Attack payloads (experiments/payloads/, garak data, etc.)
- Externally fetched content
- Any file from an untrusted source

Usage:
    python3 tools/safe_read.py <file_path> [max_len] [--no-header] [--raw-too]

Examples:
    # Default: max_len=15, with header
    python3 tools/safe_read.py experiments/payloads/P01_xml_close_reopen.txt

    # High security: max_len=9
    python3 tools/safe_read.py payload.txt 9

    # Also show raw content (for comparison/experiment)
    python3 tools/safe_read.py payload.txt 12 --raw-too

    # Read from stdin (pipe from curl, etc.)
    curl -s https://example.com | python3 tools/safe_read.py - 12
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from entropyshield import hef_pipeline


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    file_path = sys.argv[1]
    max_len = 15
    header = True
    show_raw = False

    for arg in sys.argv[2:]:
        if arg == "--no-header":
            header = False
        elif arg == "--raw-too":
            show_raw = True
        elif arg.isdigit():
            max_len = int(arg)

    # Read from file or stdin
    if file_path == "-":
        raw = sys.stdin.read()
        source = "<stdin>"
    else:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()
        source = file_path

    # Process through EntropyShield
    safe = hef_pipeline(raw, max_len=max_len, header=header)

    print(f"[safe_read] source: {source} | len: {len(raw)} | max_len: {max_len}")
    print(safe)

    if show_raw:
        print("\n--- RAW (for experiment comparison only) ---")
        print(raw)


if __name__ == "__main__":
    main()
