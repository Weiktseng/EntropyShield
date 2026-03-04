# tool_defense — Claude Code Log Security Scanner

Scans Claude Code conversation logs (`~/.claude/`) for sensitive
information leaks: API keys, connection strings, cryptographic material,
PII, and environment variable values.

Part of the [EntropyShield](https://github.com/Weiktseng/EntropyShield)
AI security toolkit.

## Quick Start

```bash
cd /path/to/EntropyShield

# Full scan (default: ~/.claude/)
python -m tool_defense

# CRITICAL findings only
python -m tool_defense -s CRITICAL

# Scan specific path
python -m tool_defense /path/to/.claude/

# Only API key category
python -m tool_defense -c "API Keys & Tokens"

# JSON report only
python -m tool_defense -f json

# List all detection patterns
python -m tool_defense --list-patterns
```

## What It Detects

| Category | Examples | Severity |
|----------|---------|----------|
| API Keys & Tokens | OpenAI, Anthropic, Google, AWS, GitHub, Stripe, Slack, HuggingFace, JWT, Bearer | CRITICAL / HIGH |
| Connection Strings | PostgreSQL, MySQL, MongoDB, Redis with embedded credentials | CRITICAL |
| Cryptographic Material | PEM private keys, PGP private keys | CRITICAL |
| PII | Email, Taiwan ID, phone numbers, credit cards (Luhn validated), private IPs | HIGH / MEDIUM |
| Environment Variables | PASSWORD=, SECRET=, API_KEY= with values | HIGH |

25 detection patterns with false-positive exclusion (Claude Code internal
identifiers, placeholder values, noreply addresses, etc.)

## Output

Reports are saved to `tool_defense/scan_output/` with:
- **chmod 600** — only you can read them
- **gitignored** — double protection (project .gitignore + directory .gitignore)
- **Redacted values** — `sk-proj-abc123xyz` → `sk-p****xyz`

Both human-readable (`.txt`) and machine-readable (`.json`) formats.

Stdout shows **counts only**, never sensitive values.

## Exit Codes

- `0` — No CRITICAL findings
- `1` — CRITICAL findings detected (useful for CI/CD integration)

## Requirements

- Python 3.10+
- Zero external dependencies (stdlib only)

## Security

See [THREAT_REPORT.md](THREAT_REPORT.md) for the full threat analysis
of Claude Code's local attack surface, including:
- Conversation log data exposure
- Permission escalation via `settings.local.json`
- MCP plugin supply chain attacks
- Local credential store access
