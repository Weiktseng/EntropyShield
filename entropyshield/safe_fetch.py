"""
Safe Fetch — URL-aware fetching with redirect inspection and content fragmentation.

Threat model:
  1. Redirect hijack: URL redirects to a different domain (phishing, payload swap)
  2. Embedded URLs: Fetched content contains signup/login/oauth links that could
     trick an LLM into generating clickable phishing links
  3. Prompt injection: Fetched content contains imperative commands

Defense:
  - Redirect chain is inspected hop-by-hop; cross-domain redirects require approval
  - URLs in content are detected and neutralized (fragmented or replaced)
  - All text content is HEF-fragmented before output
"""

import re
import sys
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .fragmenter import fragment_text

# URL patterns to flag in fetched content
_URL_RE = re.compile(
    r'https?://[^\s\'"<>\[\](){}]+', re.IGNORECASE
)

# Suspicious URL keywords — these get extra warning
_SUSPICIOUS_URL_KEYWORDS = [
    "signup", "sign-up", "sign_up",
    "login", "log-in", "log_in",
    "register", "oauth", "auth",
    "redirect", "callback",
    "confirm", "verify", "activate",
    "password", "reset", "token",
    "invite", "join",
]


@dataclass
class RedirectHop:
    """A single hop in a redirect chain."""
    status: int
    url: str
    domain: str


@dataclass
class FetchReport:
    """Result of a safe fetch operation."""
    final_url: str
    redirect_chain: list[RedirectHop] = field(default_factory=list)
    cross_domain_redirect: bool = False
    embedded_urls: list[str] = field(default_factory=list)
    suspicious_urls: list[str] = field(default_factory=list)
    raw_size: int = 0
    fragmented_content: str = ""
    warnings: list[str] = field(default_factory=list)

    def print_safety_report(self, file=sys.stderr):
        """Print a human-readable safety report before content."""
        print("=" * 60, file=file)
        print("  EntropyShield Safe Fetch Report", file=file)
        print("=" * 60, file=file)

        if self.redirect_chain:
            print(f"\n  Redirect chain ({len(self.redirect_chain)} hops):", file=file)
            for i, hop in enumerate(self.redirect_chain):
                marker = " ⚠ CROSS-DOMAIN" if (
                    i > 0 and hop.domain != self.redirect_chain[i - 1].domain
                ) else ""
                print(f"    [{hop.status}] {hop.url}{marker}", file=file)
        else:
            print(f"\n  Direct fetch (no redirects): {self.final_url}", file=file)

        if self.cross_domain_redirect:
            print(f"\n  ⚠ WARNING: Cross-domain redirect detected!", file=file)

        print(f"\n  Content size: {self.raw_size} bytes", file=file)
        print(f"  Embedded URLs found: {len(self.embedded_urls)}", file=file)

        if self.suspicious_urls:
            print(f"\n  ⚠ Suspicious URLs ({len(self.suspicious_urls)}):", file=file)
            for url in self.suspicious_urls:
                print(f"    → {url}", file=file)

        for w in self.warnings:
            print(f"\n  ⚠ {w}", file=file)

        print("=" * 60, file=file)


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    # Strip www. for comparison
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _classify_url(url: str) -> bool:
    """Return True if URL contains suspicious keywords."""
    url_lower = url.lower()
    return any(kw in url_lower for kw in _SUSPICIOUS_URL_KEYWORDS)


def _neutralize_urls(text: str) -> tuple[str, list[str], list[str]]:
    """
    Find all URLs in text. Neutralize them by fragmenting the URL itself.

    Returns:
        (neutralized_text, all_urls, suspicious_urls)
    """
    all_urls = _URL_RE.findall(text)
    suspicious = [u for u in all_urls if _classify_url(u)]

    def _neutralize(match):
        url = match.group(0)
        # Fragment the URL so it's not clickable but still readable
        parts = []
        for i in range(0, len(url), 6):
            parts.append(url[i:i + 6])
        return "[URL: " + " | ".join(parts) + "]"

    neutralized = _URL_RE.sub(_neutralize, text)
    return neutralized, all_urls, suspicious


def inspect_redirect_chain(
    url: str,
    max_hops: int = 10,
) -> list[RedirectHop]:
    """
    Follow redirects step-by-step and record each hop.
    Does NOT fetch the final body — only follows headers.

    Requires: httpx (optional dependency)

    Args:
        url:      Starting URL.
        max_hops: Maximum redirects to follow.

    Returns:
        List of RedirectHop objects.
    """
    try:
        import httpx
    except ImportError:
        raise ImportError(
            "httpx is required for safe_fetch. "
            "Install with: pip install entropyshield[fetch]"
        )

    chain = []
    current_url = url

    with httpx.Client(timeout=15, follow_redirects=False) as client:
        for _ in range(max_hops):
            resp = client.head(current_url)
            domain = _extract_domain(current_url)
            chain.append(RedirectHop(
                status=resp.status_code,
                url=current_url,
                domain=domain,
            ))

            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if not location:
                    break
                # Handle relative redirects
                if location.startswith("/"):
                    parsed = urlparse(current_url)
                    location = f"{parsed.scheme}://{parsed.netloc}{location}"
                current_url = location
            else:
                break

    return chain


def safe_fetch(
    url: str,
    max_len: int = 9,
    allow_cross_domain: bool = False,
    output_file: Optional[str] = None,
) -> FetchReport:
    """
    Fetch a URL with full safety inspection and content fragmentation.

    Pipeline:
      1. Inspect redirect chain (flag cross-domain hops)
      2. Fetch final content
      3. Convert HTML to markdown
      4. Detect and neutralize embedded URLs
      5. HEF-fragment all text content
      6. Return FetchReport with safety metadata

    Args:
        url:                 Target URL.
        max_len:             Max fragment length for HEF.
        allow_cross_domain:  If False, abort on cross-domain redirect.
        output_file:         Optional path to write fragmented output.

    Returns:
        FetchReport with safety info and fragmented content.
    """
    try:
        import httpx
        from markdownify import markdownify
    except ImportError:
        raise ImportError(
            "httpx and markdownify are required for safe_fetch. "
            "Install with: pip install entropyshield[fetch]"
        )

    report = FetchReport(final_url=url)

    # Step 1: Inspect redirects
    chain = inspect_redirect_chain(url)
    report.redirect_chain = chain

    if len(chain) > 1:
        domains = [hop.domain for hop in chain]
        unique_domains = set(domains)
        if len(unique_domains) > 1:
            report.cross_domain_redirect = True
            report.warnings.append(
                f"Cross-domain redirect: {' → '.join(domains)}"
            )
            if not allow_cross_domain:
                report.warnings.append(
                    "Fetch ABORTED. Set allow_cross_domain=True to override."
                )
                report.print_safety_report()
                return report

    final_url = chain[-1].url if chain else url
    report.final_url = final_url

    # Step 2: Fetch content
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()

    # Step 3: HTML → markdown
    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        text = markdownify(resp.text)
    else:
        text = resp.text

    report.raw_size = len(text)

    # Step 4: Neutralize embedded URLs
    text, all_urls, suspicious = _neutralize_urls(text)
    report.embedded_urls = all_urls
    report.suspicious_urls = suspicious

    if suspicious:
        report.warnings.append(
            f"{len(suspicious)} suspicious URL(s) found and neutralized "
            f"(signup/login/oauth/redirect)"
        )

    # Step 5: HEF fragment
    report.fragmented_content = fragment_text(text, max_len)

    # Step 6: Output
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            # Write safety header
            f.write("# EntropyShield Safe Fetch Output\n")
            f.write(f"# Source: {url}\n")
            f.write(f"# Final URL: {final_url}\n")
            f.write(f"# Redirects: {len(chain)} hops\n")
            f.write(f"# Cross-domain: {report.cross_domain_redirect}\n")
            f.write(f"# Embedded URLs: {len(all_urls)} "
                    f"({len(suspicious)} suspicious, neutralized)\n")
            f.write(f"# Raw size: {report.raw_size} bytes\n")
            f.write("#\n# Content below is HEF-fragmented.\n\n")
            f.write(report.fragmented_content)

    report.print_safety_report()
    return report
