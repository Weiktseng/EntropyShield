"""
CLI entry point for EntropyShield.

Usage:
  python -m entropyshield <url> [output_file]   Safe fetch + fragment
  python -m entropyshield --pipe                 Shield stdin → stdout
  python -m entropyshield --mcp                  Start MCP server
  python -m entropyshield --setup                Install MCP + auto-approve permissions
"""

import sys


def _setup():
    """One-command setup: add MCP server + write global auto-approve permission."""
    import json
    import os
    import shutil
    import subprocess

    settings_path = os.path.expanduser("~/.claude/settings.local.json")
    mcp_rule = "mcp__entropyshield__*"

    # Step 1: Add MCP server
    claude_bin = shutil.which("claude")
    if claude_bin:
        print("[1/2] Adding EntropyShield MCP server...")
        subprocess.run(
            [claude_bin, "mcp", "add", "entropyshield", "--", sys.executable, "-m", "entropyshield", "--mcp"],
            check=False,
        )
    else:
        print("[1/2] 'claude' CLI not found — skip MCP add.")
        print("       Run manually: claude mcp add entropyshield -- python -m entropyshield --mcp")

    # Step 2: Add permission to global settings
    print(f"[2/2] Writing auto-approve permission to {settings_path}...")

    os.makedirs(os.path.dirname(settings_path), exist_ok=True)

    settings = {}
    if os.path.exists(settings_path):
        with open(settings_path) as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}

    perms = settings.setdefault("permissions", {})
    allow = perms.setdefault("allow", [])

    if mcp_rule not in allow:
        allow.append(mcp_rule)
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
            f.write("\n")
        print(f"       Added '{mcp_rule}' to allow list.")
    else:
        print(f"       '{mcp_rule}' already in allow list.")

    print()
    print("Done! Restart Claude Code to activate.")
    print("EntropyShield tools (shield_text, shield_read, shield_fetch)")
    print("will now run automatically without permission prompts.")


def main():
    if len(sys.argv) < 2:
        print("EntropyShield — Prompt Injection Defense")
        print()
        print("Usage:")
        print("  python -m entropyshield <url> [output_file]  Fetch & shield URL")
        print("  python -m entropyshield --pipe               Shield stdin → stdout")
        print("  python -m entropyshield --mcp                Start MCP server")
        print("  python -m entropyshield --setup              Install MCP + auto-approve")
        print()
        print("Options:")
        print("  --allow-cross-domain   Allow cross-domain redirects")
        print("  --max-len N            Max fragment length (default: 9)")
        return

    args = sys.argv[1:]

    # --setup: one-command install
    if "--setup" in args:
        _setup()
        return

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
