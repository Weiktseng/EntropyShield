"""
Sensitive data detection patterns for Claude Code conversation log scanning.

Defines regex patterns, severity levels, categories, and false-positive
exclusion rules for identifying leaked secrets in JSONL conversation logs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    def __ge__(self, other: Severity) -> bool:
        order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        return order[self] >= order[other]

    def __gt__(self, other: Severity) -> bool:
        order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        return order[self] > order[other]

    def __le__(self, other: Severity) -> bool:
        order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        return order[self] <= order[other]

    def __lt__(self, other: Severity) -> bool:
        order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2, Severity.CRITICAL: 3}
        return order[self] < order[other]


class Category(Enum):
    API_KEY = "API Keys & Tokens"
    CONNECTION_STRING = "Connection Strings"
    CRYPTO_MATERIAL = "Cryptographic Material"
    PII = "Personal Identifiable Information"
    ENV_VARIABLE = "Environment Variable Values"


@dataclass(frozen=True)
class SensitivePattern:
    """A single detection pattern with metadata."""

    name: str
    regex: re.Pattern[str]
    severity: Severity
    category: Category
    description: str
    false_positive_patterns: tuple[re.Pattern[str], ...] = ()
    min_match_length: int = 0


# ---------------------------------------------------------------------------
# Pre-compiled false-positive patterns
# ---------------------------------------------------------------------------

_FP_CLAUDE_INTERNAL_SK = re.compile(
    r"^sk-(?:notification|output-waiting|ant-api)"
)
_FP_SK_TOO_SHORT = re.compile(r"^sk-[A-Za-z0-9_-]{0,7}$")
_FP_NOREPLY_EMAIL = re.compile(r"(?:noreply|no-reply|example|test|users\.noreply)@", re.IGNORECASE)
_FP_EXAMPLE_DOMAIN = re.compile(r"@(?:example\.com|test\.com|localhost|users\.noreply\.github\.com)", re.IGNORECASE)
_FP_GIT_SSH = re.compile(r"git@")
_FP_PLACEHOLDER_VALUE = re.compile(
    r"(?:your[_-]|example|changeme|xxx|placeholder|TODO|<|REPLACE)", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# All built-in patterns
# ---------------------------------------------------------------------------

_DEFAULT_PATTERNS: list[SensitivePattern] = [
    # ===== API Keys & Tokens (CRITICAL) =====
    SensitivePattern(
        name="openai_api_key",
        regex=re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="OpenAI API key (sk-proj-... or sk-...)",
        false_positive_patterns=(_FP_CLAUDE_INTERNAL_SK, _FP_SK_TOO_SHORT),
    ),
    SensitivePattern(
        name="anthropic_api_key",
        regex=re.compile(r"sk-ant-(?:api\d{2}-)?[A-Za-z0-9_-]{20,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="Anthropic API key (sk-ant-...)",
    ),
    SensitivePattern(
        name="google_api_key",
        regex=re.compile(r"AIza[A-Za-z0-9_-]{35}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="Google API key (AIza...)",
    ),
    SensitivePattern(
        name="aws_access_key",
        regex=re.compile(r"AKIA[A-Z0-9]{16}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="AWS Access Key ID (AKIA...)",
    ),
    SensitivePattern(
        name="github_token",
        regex=re.compile(r"(?:ghp|gho|ghs|ghr)_[A-Za-z0-9_]{36,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="GitHub personal access token",
    ),
    SensitivePattern(
        name="github_pat",
        regex=re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="GitHub fine-grained PAT",
    ),
    SensitivePattern(
        name="stripe_key",
        regex=re.compile(r"(?:sk|pk|rk)_live_[A-Za-z0-9]{20,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="Stripe live key",
    ),
    SensitivePattern(
        name="slack_token",
        regex=re.compile(r"xox[bpars]-[A-Za-z0-9-]{10,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="Slack token (xoxb-/xoxp-/...)",
    ),
    SensitivePattern(
        name="huggingface_token",
        regex=re.compile(r"hf_[A-Za-z0-9]{20,}"),
        severity=Severity.CRITICAL,
        category=Category.API_KEY,
        description="Hugging Face API token",
    ),
    SensitivePattern(
        name="vercel_token",
        regex=re.compile(r"vercel_[A-Za-z0-9_-]{20,}"),
        severity=Severity.HIGH,
        category=Category.API_KEY,
        description="Vercel token",
    ),
    SensitivePattern(
        name="supabase_key",
        regex=re.compile(r"sbp_[A-Za-z0-9]{20,}"),
        severity=Severity.HIGH,
        category=Category.API_KEY,
        description="Supabase service key",
    ),

    # ===== Tokens (HIGH) =====
    SensitivePattern(
        name="jwt_token",
        regex=re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        severity=Severity.HIGH,
        category=Category.API_KEY,
        description="JSON Web Token",
    ),
    SensitivePattern(
        name="bearer_token",
        regex=re.compile(r"Bearer\s+[A-Za-z0-9_.\-/+=]{20,}"),
        severity=Severity.HIGH,
        category=Category.API_KEY,
        description="Bearer token in Authorization header",
    ),
    SensitivePattern(
        name="authorization_header",
        regex=re.compile(r"Authorization:\s*(?:Bearer|Basic|Token)\s+[A-Za-z0-9_.\-/+=]{10,}"),
        severity=Severity.HIGH,
        category=Category.API_KEY,
        description="Authorization header value",
    ),

    # ===== Connection Strings (CRITICAL) =====
    SensitivePattern(
        name="database_connection_string",
        regex=re.compile(
            r"(?:postgresql|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)://"
            r"[^\s:]+:[^\s@]+@[^\s]+"
        ),
        severity=Severity.CRITICAL,
        category=Category.CONNECTION_STRING,
        description="Database connection string with credentials",
    ),
    SensitivePattern(
        name="generic_connection_string",
        regex=re.compile(r"://[A-Za-z0-9._-]+:[^\s@]{3,}@[A-Za-z0-9._-]+"),
        severity=Severity.HIGH,
        category=Category.CONNECTION_STRING,
        description="Generic connection string with user:password@host",
        false_positive_patterns=(_FP_GIT_SSH,),
    ),

    # ===== Cryptographic Material (CRITICAL) =====
    SensitivePattern(
        name="private_key_pem",
        regex=re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        severity=Severity.CRITICAL,
        category=Category.CRYPTO_MATERIAL,
        description="PEM-encoded private key",
    ),
    SensitivePattern(
        name="pgp_private_key",
        regex=re.compile(r"-----BEGIN PGP PRIVATE KEY(?: BLOCK)?-----"),
        severity=Severity.CRITICAL,
        category=Category.CRYPTO_MATERIAL,
        description="PGP private key",
    ),

    # ===== PII (MEDIUM / HIGH) =====
    SensitivePattern(
        name="email_address",
        regex=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        severity=Severity.MEDIUM,
        category=Category.PII,
        description="Email address",
        false_positive_patterns=(_FP_NOREPLY_EMAIL, _FP_EXAMPLE_DOMAIN),
    ),
    SensitivePattern(
        name="taiwan_id",
        regex=re.compile(r"\b[A-Z][12]\d{8}\b"),
        severity=Severity.HIGH,
        category=Category.PII,
        description="Taiwan National ID number",
        min_match_length=10,
    ),
    SensitivePattern(
        name="taiwan_phone",
        regex=re.compile(r"\b09\d{2}-?\d{3}-?\d{3}\b"),
        severity=Severity.MEDIUM,
        category=Category.PII,
        description="Taiwan mobile phone number",
    ),
    SensitivePattern(
        name="credit_card",
        regex=re.compile(r"\b(?:\d{4}[- ]?){3}\d{4}\b"),
        severity=Severity.HIGH,
        category=Category.PII,
        description="Credit card number (Luhn validated)",
    ),
    SensitivePattern(
        name="private_ip_address",
        regex=re.compile(
            r"\b(?:192\.168\.\d{1,3}\.\d{1,3}"
            r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
        ),
        severity=Severity.LOW,
        category=Category.PII,
        description="Private IP address",
    ),

    # ===== Environment Variable Values (HIGH) =====
    SensitivePattern(
        name="env_secret_assignment",
        regex=re.compile(
            r"(?:PASSWORD|SECRET|TOKEN|API_KEY|APIKEY|API_SECRET"
            r"|ACCESS_KEY|PRIVATE_KEY|AUTH_TOKEN|CLIENT_SECRET"
            r"|DATABASE_URL|DB_PASSWORD|ENCRYPTION_KEY"
            r")\s*[=:]\s*[\"']?[^\s\"']{8,}",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        category=Category.ENV_VARIABLE,
        description="Environment variable with secret-like name and value",
        false_positive_patterns=(_FP_PLACEHOLDER_VALUE,),
    ),
    SensitivePattern(
        name="inline_password_assignment",
        regex=re.compile(
            r"(?:password|passwd|secret)\s*=\s*[\"'][^\"']{8,}[\"']",
            re.IGNORECASE,
        ),
        severity=Severity.HIGH,
        category=Category.ENV_VARIABLE,
        description="Inline password/secret assignment in code",
        false_positive_patterns=(_FP_PLACEHOLDER_VALUE,),
    ),
]


class PatternRegistry:
    """Registry of all sensitive data detection patterns."""

    def __init__(self) -> None:
        self._patterns: list[SensitivePattern] = list(_DEFAULT_PATTERNS)

    def get_patterns(
        self,
        severity: Severity | None = None,
        category: Category | None = None,
    ) -> list[SensitivePattern]:
        """Return patterns, optionally filtered by severity or category."""
        result = self._patterns
        if severity is not None:
            result = [p for p in result if p.severity >= severity]
        if category is not None:
            result = [p for p in result if p.category == category]
        return result

    @staticmethod
    def is_false_positive(pattern: SensitivePattern, match_text: str) -> bool:
        """Check if a match is a known false positive."""
        if pattern.min_match_length and len(match_text) < pattern.min_match_length:
            return True
        for fp in pattern.false_positive_patterns:
            if fp.search(match_text):
                return True
        return False
