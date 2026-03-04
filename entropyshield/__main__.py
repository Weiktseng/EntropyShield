"""
CLI entry point for EntropyShield.

Usage:
  python -m entropyshield <url> [output_file]   Safe fetch + fragment
  python -m entropyshield --pipe                 Shield stdin → stdout
  python -m entropyshield --mcp                  Start MCP server
"""

import sys


def main():
    if len(sys.argv) < 2:
        print("EntropyShield — Prompt Injection Defense")
        print()
        print("Usage:")
        print("  python -m entropyshield <url> [output_file]  Fetch & shield URL")
        print("  python -m entropyshield --pipe               Shield stdin → stdout")
        print("  python -m entropyshield --mcp                Start MCP server")
        print()
        print("Options:")
        print("  --allow-cross-domain   Allow cross-domain redirects")
        print("  --max-len N            Max fragment length (default: 9)")
        return

    args = sys.argv[1:]

    # --mcp: start MCP server
    if "--mcp" in args:
        from .mcp_server import main as mcp_main
        mcp_main()
        return

    # --pipe: shield stdin → stdout
    if "--pipe" in args:
        from .shield import shield
        text = sys.stdin.read()
        if text.strip():
            print(shield(text))
        return

    allow_cross = "--allow-cross-domain" in args
    if allow_cross:
        args.remove("--allow-cross-domain")

    max_len = 9
    if "--max-len" in args:
        idx = args.index("--max-len")
        max_len = int(args[idx + 1])
        args.pop(idx + 1)
        args.pop(idx)

    url = args[0]
    output_file = args[1] if len(args) > 1 else None

    from .safe_fetch import safe_fetch

    report = safe_fetch(
        url=url,
        max_len=max_len,
        allow_cross_domain=allow_cross,
        output_file=output_file,
    )

    if not output_file and report.fragmented_content:
        print(report.fragmented_content)


if __name__ == "__main__":
    main()
