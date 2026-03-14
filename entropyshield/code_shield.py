"""
EntropyShield Code-Aware Shield — shield_read_code

Intelligently shields source code files:
  - CODE regions → pass through (AI can analyze logic)
  - COMMENTS → shield() (prompt injection can hide here)
  - STRING LITERALS → shield() (prompt injection can hide here)
  - Obfuscation patterns → warn (base64, eval, exec)

For binary files:
  - Extract printable strings, shield them, report metadata

Usage:
    from entropyshield.code_shield import shield_code_file
    result = shield_code_file("/path/to/suspicious_package/setup.py")
"""

from __future__ import annotations

import hashlib
import io
import re
import tokenize as py_tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Language configuration
# ---------------------------------------------------------------------------

@dataclass
class LangConfig:
    line_comment: Optional[str] = None
    block_comment: Optional[tuple[str, str]] = None
    string_delims: list[str] = field(default_factory=lambda: ['"', "'"])
    triple_string: bool = False
    raw_string_prefixes: str = ""


LANG_CONFIGS: dict[str, LangConfig] = {
    # Python — uses built-in tokenize module instead of regex
    ".py": LangConfig(line_comment="#", triple_string=True, raw_string_prefixes="rbRBuUfF"),
    ".pyw": LangConfig(line_comment="#", triple_string=True, raw_string_prefixes="rbRBuUfF"),
    # JavaScript / TypeScript
    ".js": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'", "`"]),
    ".jsx": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'", "`"]),
    ".ts": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'", "`"]),
    ".tsx": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'", "`"]),
    ".mjs": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'", "`"]),
    # C-family
    ".c": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    ".h": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    ".cpp": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    ".hpp": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    ".cc": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    # Java / Kotlin
    ".java": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    ".kt": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    # Go
    ".go": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "`"]),
    # Rust
    ".rs": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    # Ruby
    ".rb": LangConfig(line_comment="#", block_comment=("=begin", "=end"), string_delims=['"', "'"]),
    # Shell
    ".sh": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".bash": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".zsh": LangConfig(line_comment="#", string_delims=['"', "'"]),
    # PHP
    ".php": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'"]),
    # SQL
    ".sql": LangConfig(line_comment="--", block_comment=("/*", "*/"), string_delims=["'"]),
    # Swift
    ".swift": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"']),
    # Perl
    ".pl": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".pm": LangConfig(line_comment="#", string_delims=['"', "'"]),
    # R
    ".r": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".R": LangConfig(line_comment="#", string_delims=['"', "'"]),
    # Lua
    ".lua": LangConfig(line_comment="--", block_comment=("--[[", "]]"), string_delims=['"', "'"]),
    # HTML / XML
    ".html": LangConfig(block_comment=("<!--", "-->"), string_delims=['"', "'"]),
    ".htm": LangConfig(block_comment=("<!--", "-->"), string_delims=['"', "'"]),
    ".xml": LangConfig(block_comment=("<!--", "-->"), string_delims=['"', "'"]),
    ".svg": LangConfig(block_comment=("<!--", "-->"), string_delims=['"', "'"]),
    # CSS
    ".css": LangConfig(block_comment=("/*", "*/"), string_delims=['"', "'"]),
    ".scss": LangConfig(line_comment="//", block_comment=("/*", "*/"), string_delims=['"', "'"]),
    # YAML / TOML / INI
    ".yaml": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".yml": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".toml": LangConfig(line_comment="#", string_delims=['"', "'"]),
    ".ini": LangConfig(line_comment=";", string_delims=['"', "'"]),
    # Makefile / Dockerfile
    ".mk": LangConfig(line_comment="#"),
    "Makefile": LangConfig(line_comment="#"),
    "Dockerfile": LangConfig(line_comment="#"),
}


# ---------------------------------------------------------------------------
# Obfuscation detection
# ---------------------------------------------------------------------------

OBFUSCATION_PATTERNS = [
    (re.compile(r'base64\.(b64decode|decodebytes)'), "base64 decoding"),
    (re.compile(r'eval\s*\('), "eval() call"),
    (re.compile(r'exec\s*\('), "exec() call"),
    (re.compile(r'__import__\s*\('), "dynamic __import__()"),
    (re.compile(r'(?:\\x[0-9a-fA-F]{2}){4,}'), "hex-encoded bytes"),
    (re.compile(r'codecs\.decode'), "codecs.decode (encoding evasion)"),
    (re.compile(r'compile\s*\(.*["\']exec["\']'), "compile() with exec mode"),
    (re.compile(r'getattr\s*\(.*["\']__'), "dunder access via getattr"),
    (re.compile(r'fromCharCode'), "String.fromCharCode (JS)"),
    (re.compile(r'atob\s*\('), "atob() base64 decode (JS)"),
    (re.compile(r'Buffer\.from\s*\(.*base64'), "Buffer.from base64 (Node.js)"),
    (re.compile(r'subprocess\.(run|call|Popen|check_output)\s*\('), "subprocess call"),
    (re.compile(r'os\.system\s*\('), "os.system() call"),
    (re.compile(r'ctypes\.(cdll|windll|CDLL)'), "ctypes native library loading"),
    (re.compile(r'socket\.(socket|connect|send)\s*\('), "raw socket usage"),
    (re.compile(r'requests\.(get|post)\s*\('), "HTTP request"),
    (re.compile(r'urllib\.request\.urlopen\s*\('), "urllib request"),
]

# ---------------------------------------------------------------------------
# Binary file detection
# ---------------------------------------------------------------------------

MAGIC_BYTES = {
    b'\x7fELF': 'ELF',
    b'\xcf\xfa\xed\xfe': 'Mach-O 64-bit',
    b'\xce\xfa\xed\xfe': 'Mach-O 32-bit',
    b'\xfe\xed\xfa\xcf': 'Mach-O 64-bit (BE)',
    b'\xfe\xed\xfa\xce': 'Mach-O 32-bit (BE)',
    b'MZ': 'PE (Windows)',
    b'\x00asm': 'WebAssembly',
    b'PK': 'ZIP/JAR/WHL',
}

BINARY_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dll', '.dylib', '.exe',
    '.o', '.a', '.lib', '.wasm',
    '.class', '.jar', '.war',
    '.whl', '.egg', '.zip', '.gz', '.tar', '.bz2', '.xz',
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.mp3', '.mp4', '.wav', '.avi', '.mov',
}


# ---------------------------------------------------------------------------
# Core: Python tokenizer (precise)
# ---------------------------------------------------------------------------

def _shield_python_file(content: str) -> tuple[str, list[str]]:
    """
    Use Python's built-in tokenize module for precise comment/string detection.
    Returns (shielded_source, warnings).
    """
    from .shield import shield

    warnings = []
    # Collect regions to shield: list of (start_offset, end_offset, replacement)
    regions_to_shield: list[tuple[int, int, str]] = []

    lines = content.splitlines(keepends=True)
    if not lines:
        return content, warnings

    try:
        tokens = list(py_tokenize.generate_tokens(io.StringIO(content).readline))
    except py_tokenize.TokenError:
        # Incomplete or malformed Python — fall back to generic
        lang = LANG_CONFIGS.get(".py")
        return _shield_generic_file(content, lang), _detect_obfuscation(content)

    for tok in tokens:
        if tok.type in (py_tokenize.COMMENT, py_tokenize.STRING):
            # Convert (row, col) to absolute offset
            start_row, start_col = tok.start
            end_row, end_col = tok.end
            tok_str = tok.string

            if tok.type == py_tokenize.COMMENT:
                # Shield comment content but keep the #
                comment_body = tok_str[1:]  # remove #
                shielded_body = shield(comment_body) if comment_body.strip() else comment_body
                regions_to_shield.append((
                    _pos_to_offset(lines, start_row, start_col),
                    _pos_to_offset(lines, end_row, end_col),
                    "#" + shielded_body,
                ))
            else:
                # STRING token — shield the content inside quotes
                shielded_str = _shield_string_token(tok_str, shield)
                regions_to_shield.append((
                    _pos_to_offset(lines, start_row, start_col),
                    _pos_to_offset(lines, end_row, end_col),
                    shielded_str,
                ))

    # Detect obfuscation in code regions (not comments/strings)
    warnings = _detect_obfuscation_with_lines(content, lines, regions_to_shield)

    # Apply replacements in reverse order to preserve offsets
    result = content
    for start, end, replacement in sorted(regions_to_shield, key=lambda x: x[0], reverse=True):
        result = result[:start] + replacement + result[end:]

    return result, warnings


def _pos_to_offset(lines: list[str], row: int, col: int) -> int:
    """Convert (1-based row, 0-based col) to absolute string offset."""
    offset = 0
    for i in range(row - 1):
        if i < len(lines):
            offset += len(lines[i])
    return offset + col


def _shield_string_token(tok_str: str, shield_fn) -> str:
    """Shield the content inside a string literal, preserving quote delimiters."""
    # Detect prefix (r, b, f, u, rb, etc.) and quote style
    prefix = ""
    rest = tok_str
    while rest and rest[0] in "rRbBuUfF":
        prefix += rest[0]
        rest = rest[1:]

    # Detect triple or single quote
    if rest.startswith('"""') or rest.startswith("'''"):
        quote = rest[:3]
        inner = rest[3:-3]
    elif rest and rest[0] in ('"', "'"):
        quote = rest[0]
        inner = rest[1:-1]
    else:
        return tok_str  # weird case, return as-is

    if inner.strip():
        shielded_inner = shield_fn(inner)
    else:
        shielded_inner = inner

    return prefix + quote + shielded_inner + quote


# ---------------------------------------------------------------------------
# Core: Generic tokenizer (regex state machine)
# ---------------------------------------------------------------------------

def _shield_generic_file(content: str, config: LangConfig) -> str:
    """
    State-machine tokenizer for non-Python languages.
    Identifies comment and string regions, shields them.
    """
    from .shield import shield

    result = []
    i = 0
    n = len(content)

    while i < n:
        matched = False

        # Check block comment
        if config.block_comment:
            start_delim, end_delim = config.block_comment
            if content[i:i + len(start_delim)] == start_delim:
                end_pos = content.find(end_delim, i + len(start_delim))
                if end_pos == -1:
                    end_pos = n - len(end_delim)
                comment_body = content[i + len(start_delim):end_pos]
                shielded = shield(comment_body) if comment_body.strip() else comment_body
                result.append(start_delim + shielded + end_delim)
                i = end_pos + len(end_delim)
                matched = True

        # Check line comment
        if not matched and config.line_comment:
            lc = config.line_comment
            if content[i:i + len(lc)] == lc:
                # Make sure it's not inside a string (simple heuristic)
                end_pos = content.find("\n", i)
                if end_pos == -1:
                    end_pos = n
                comment_body = content[i + len(lc):end_pos]
                shielded = shield(comment_body) if comment_body.strip() else comment_body
                result.append(lc + shielded)
                if end_pos < n:
                    result.append("\n")
                i = end_pos + 1 if end_pos < n else n
                matched = True

        # Check string literals
        if not matched:
            for delim in config.string_delims:
                # Check for triple-quote (only if the delim is " or ')
                triple = delim * 3 if len(delim) == 1 and config.triple_string else None
                if triple and content[i:i + 3] == triple:
                    end_pos = content.find(triple, i + 3)
                    if end_pos == -1:
                        end_pos = n - 3
                    inner = content[i + 3:end_pos]
                    shielded = shield(inner) if inner.strip() else inner
                    result.append(triple + shielded + triple)
                    i = end_pos + 3
                    matched = True
                    break
                elif content[i:i + len(delim)] == delim:
                    # Find end of string, respecting escapes
                    j = i + len(delim)
                    while j < n:
                        if content[j] == '\\':
                            j += 2  # skip escaped char
                        elif content[j:j + len(delim)] == delim:
                            j += len(delim)
                            break
                        elif delim != '`' and content[j] == '\n':
                            # Single-line strings end at newline (except backtick)
                            break
                        else:
                            j += 1
                    else:
                        j = n

                    inner = content[i + len(delim):j - len(delim)] if j <= n else content[i + len(delim):]
                    shielded = shield(inner) if inner.strip() else inner
                    if j <= n and j - len(delim) >= i + len(delim):
                        result.append(delim + shielded + delim)
                    else:
                        result.append(delim + shielded)
                    i = j
                    matched = True
                    break

        if not matched:
            result.append(content[i])
            i += 1

    return "".join(result)


# ---------------------------------------------------------------------------
# Obfuscation detection
# ---------------------------------------------------------------------------

def _detect_obfuscation(content: str) -> list[str]:
    """Scan content for obfuscation patterns, return warnings."""
    warnings = []
    for pattern, desc in OBFUSCATION_PATTERNS:
        matches = list(pattern.finditer(content))
        if matches:
            lines_seen = set()
            for m in matches:
                line_num = content[:m.start()].count('\n') + 1
                lines_seen.add(line_num)
            for ln in sorted(lines_seen):
                warnings.append(f"Line {ln}: {desc}")
    return warnings


def _detect_obfuscation_with_lines(
    content: str,
    lines: list[str],
    shielded_regions: list[tuple[int, int, str]],
) -> list[str]:
    """Detect obfuscation only in CODE regions (outside comments/strings)."""
    # Build set of shielded ranges
    shielded_ranges = [(s, e) for s, e, _ in shielded_regions]

    warnings = []
    for pattern, desc in OBFUSCATION_PATTERNS:
        for m in pattern.finditer(content):
            pos = m.start()
            # Skip if inside a shielded region
            in_shielded = any(s <= pos < e for s, e in shielded_ranges)
            if not in_shielded:
                line_num = content[:pos].count('\n') + 1
                warnings.append(f"Line {line_num}: {desc}")

    return warnings


# ---------------------------------------------------------------------------
# Binary file handling
# ---------------------------------------------------------------------------

def _detect_binary_format(data: bytes) -> Optional[str]:
    """Detect binary format from magic bytes."""
    for magic, fmt in MAGIC_BYTES.items():
        if data[:len(magic)] == magic:
            return fmt
    return None


def _extract_strings(data: bytes, min_len: int = 6) -> list[str]:
    """Extract printable ASCII strings from binary data (like Unix `strings`)."""
    result = []
    current: list[str] = []
    for byte in data:
        if 32 <= byte < 127:
            current.append(chr(byte))
        else:
            if len(current) >= min_len:
                result.append("".join(current))
            current = []
    if len(current) >= min_len:
        result.append("".join(current))
    return result


def _shield_binary(file_path: Path) -> str:
    """Handle binary files: detect format, extract strings, shield them."""
    from .shield import shield

    data = file_path.read_bytes()
    fmt = _detect_binary_format(data) or "Unknown binary"
    size = len(data)
    sha256 = hashlib.sha256(data).hexdigest()[:16]

    header = (
        f"[EntropyShield Binary Analysis: {file_path.name}]\n"
        f"Format: {fmt} | Size: {_human_size(size)} | SHA-256: {sha256}...\n"
    )

    # Try .pyc decompilation
    if file_path.suffix in ('.pyc', '.pyo'):
        source = _try_decompile_pyc(file_path)
        if source:
            shielded, warnings = _shield_python_file(source)
            warn_text = ""
            if warnings:
                warn_text = "\n⚠ WARNINGS:\n" + "\n".join(f"  - {w}" for w in warnings) + "\n"
            return (
                f"[EntropyShield Code Analysis: {file_path.name} (decompiled)]\n"
                f"Language: Python (decompiled from .pyc) | SHA-256: {sha256}...\n"
                f"{warn_text}\n"
                f"─── Shielded Source ───\n{shielded}"
            )

    # Extract strings
    strings = _extract_strings(data)
    if not strings:
        return (
            header
            + "\n⚠ Binary file — no readable strings found.\n"
            + "Cannot analyze code logic from binary."
        )

    # Shield extracted strings
    shielded_strings = []
    for s in strings[:500]:  # cap at 500 strings
        shielded_strings.append(shield(s))

    return (
        header
        + f"\n⚠ Binary file — code logic cannot be directly analyzed.\n"
        + f"Extracted {len(strings)} printable strings (shielded below).\n\n"
        + "─── Shielded Strings ───\n"
        + "\n".join(shielded_strings)
    )


def _try_decompile_pyc(path: Path) -> Optional[str]:
    """Try to decompile .pyc to Python source. Returns None if tools unavailable."""
    # Try uncompyle6
    try:
        import uncompyle6
        out = io.StringIO()
        uncompyle6.decompile_file(str(path), out)
        return out.getvalue()
    except (ImportError, Exception):
        pass
    # Try decompile3
    try:
        import decompile3
        out = io.StringIO()
        decompile3.decompile_file(str(path), out)
        return out.getvalue()
    except (ImportError, Exception):
        pass
    return None


def _human_size(nbytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB'):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}" if unit != 'B' else f"{nbytes} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


# ---------------------------------------------------------------------------
# JSON structured data
# ---------------------------------------------------------------------------

def _shield_json_file(content: str) -> str:
    """Shield string values in JSON while preserving keys and structure."""
    import json as json_mod
    from .shield import shield

    try:
        data = json_mod.loads(content)
    except json_mod.JSONDecodeError:
        # Not valid JSON, full shield
        return shield(content)

    def walk(obj):
        if isinstance(obj, str):
            return shield(obj) if obj.strip() else obj
        elif isinstance(obj, dict):
            return {k: walk(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [walk(item) for item in obj]
        return obj

    shielded = walk(data)
    return json_mod.dumps(shielded, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

def _detect_file_type(path: Path) -> str:
    """Detect file type: 'source', 'binary', 'json', 'text'."""
    suffix = path.suffix.lower()
    name = path.name

    # Check binary by extension first
    if suffix in BINARY_EXTENSIONS:
        return "binary"

    # Check language config
    if suffix in LANG_CONFIGS or name in LANG_CONFIGS:
        if suffix == ".json":
            return "json"
        return "source"

    # JSON
    if suffix == ".json":
        return "json"

    # Try reading as text to detect binary
    try:
        data = path.read_bytes()[:8192]
        # If more than 10% non-text bytes, likely binary
        non_text = sum(1 for b in data if b < 8 or (14 <= b < 32))
        if len(data) > 0 and non_text / len(data) > 0.1:
            return "binary"
    except OSError:
        pass

    return "text"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def shield_code_file(file_path: str) -> str:
    """
    Read a source code or binary file with code-aware shielding.

    - Source code: shields comments and strings, preserves code logic
    - Binary: extracts and shields printable strings
    - JSON: shields string values, preserves keys
    - Other text: full shield

    Returns formatted analysis string.
    """
    from .shield import shield

    path = Path(file_path)

    if not path.exists():
        return f"[EntropyShield] Error: file not found: {file_path}"

    if not path.is_file():
        return f"[EntropyShield] Error: not a file: {file_path}"

    file_type = _detect_file_type(path)

    # --- Binary ---
    if file_type == "binary":
        return _shield_binary(path)

    # --- Read as text ---
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return f"[EntropyShield] Error reading file: {e}"

    if not content.strip():
        return f"[EntropyShield Code Analysis: {path.name}]\n(empty file)"

    # --- JSON ---
    if file_type == "json":
        shielded = _shield_json_file(content)
        line_count = content.count('\n') + 1
        size = len(content.encode('utf-8'))
        return (
            f"[EntropyShield Code Analysis: {path.name}]\n"
            f"Format: JSON | Lines: {line_count} | Size: {_human_size(size)}\n\n"
            f"─── Shielded Content (keys preserved, values shielded) ───\n{shielded}"
        )

    # --- Source code ---
    if file_type == "source":
        suffix = path.suffix.lower()
        config = LANG_CONFIGS.get(suffix) or LANG_CONFIGS.get(path.name)
        lang_name = _lang_name(suffix, path.name)
        line_count = content.count('\n') + 1
        size = len(content.encode('utf-8'))

        # Use Python's tokenize for .py files
        if suffix in ('.py', '.pyw'):
            shielded, warnings = _shield_python_file(content)
        else:
            shielded = _shield_generic_file(content, config)
            warnings = _detect_obfuscation(content)

        warn_text = ""
        if warnings:
            warn_text = "\n⚠ WARNINGS:\n" + "\n".join(f"  - {w}" for w in warnings) + "\n"

        return (
            f"[EntropyShield Code Analysis: {path.name}]\n"
            f"Language: {lang_name} | Lines: {line_count} | Size: {_human_size(size)}\n"
            f"{warn_text}\n"
            f"─── Shielded Source (code preserved, comments/strings shielded) ───\n{shielded}"
        )

    # --- Plain text fallback ---
    shielded = shield(content)
    return (
        f"[EntropyShield Text Analysis: {path.name}]\n\n"
        f"─── Shielded Content ───\n{shielded}"
    )


def _lang_name(suffix: str, filename: str) -> str:
    """Human-readable language name from extension."""
    names = {
        ".py": "Python", ".pyw": "Python",
        ".js": "JavaScript", ".jsx": "JSX", ".mjs": "JavaScript",
        ".ts": "TypeScript", ".tsx": "TSX",
        ".c": "C", ".h": "C/C++ Header", ".cpp": "C++", ".hpp": "C++ Header", ".cc": "C++",
        ".java": "Java", ".kt": "Kotlin",
        ".go": "Go", ".rs": "Rust",
        ".rb": "Ruby", ".php": "PHP",
        ".sh": "Shell", ".bash": "Bash", ".zsh": "Zsh",
        ".sql": "SQL", ".swift": "Swift",
        ".pl": "Perl", ".pm": "Perl",
        ".r": "R", ".R": "R",
        ".lua": "Lua",
        ".html": "HTML", ".htm": "HTML", ".xml": "XML", ".svg": "SVG",
        ".css": "CSS", ".scss": "SCSS",
        ".yaml": "YAML", ".yml": "YAML",
        ".toml": "TOML", ".ini": "INI",
    }
    return names.get(suffix, filename)
