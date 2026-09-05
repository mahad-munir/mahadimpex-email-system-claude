"""
Mahad Impex Email Marketing System — Email Verifier
Validates email addresses using DNS MX lookup and SMTP probing.
"""

import re
import socket
import smtplib
import dns.resolver
import logging
from config import LOG_DIR

logger = logging.getLogger(__name__)

# Known disposable email domains (subset — enough to catch most)
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "dispostable.com", "trashmail.com", "fakeinbox.com", "maildrop.cc",
    "10minutemail.com", "temp-mail.org", "getnada.com", "mohmal.com",
    "burnermail.io", "mailnesia.com", "harakirimail.com",
    "33mail.com", "tempail.com", "discard.email",
}

# Regex for basic email format validation
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def is_valid_format(email: str) -> bool:
    """Check if email matches basic format rules."""
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def is_disposable(email: str) -> bool:
    """Check if the domain is a known disposable email provider."""
    try:
        domain = email.strip().lower().split("@")[1]
        return domain in DISPOSABLE_DOMAINS
    except (IndexError, AttributeError):
        return True


def has_mx_record(domain: str) -> bool:
    """Check if the domain has valid MX records (accepts email)."""
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        return len(mx_records) > 0
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, dns.resolver.Timeout,
            Exception):
        return False


def smtp_probe(email: str, timeout: int = 10) -> bool:
    """
    Probe the SMTP server to check if the address exists.
    Uses RCPT TO without actually sending.
    Returns True if address appears valid, False if rejected.
    Returns True on inconclusive (we'd rather keep a lead than miss one).
    """
    domain = email.strip().lower().split("@")[1]
    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        mx_host = str(sorted(mx_records, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception:
        return False

    try:
        server = smtplib.SMTP(timeout=timeout)
        server.connect(mx_host, 25)
        server.helo("mahadimpex.com")
        server.mail("verify@mahadimpex.com")
        code, _ = server.rcpt(email)
        server.quit()
        # 250 = valid, 251 = forwarded (still valid)
        # 550/551/552/553 = rejected
        return code in (250, 251)
    except smtplib.SMTPServerDisconnected:
        # Server disconnected — can't determine, assume valid
        return True
    except (smtplib.SMTPConnectError, socket.timeout, OSError):
        # Connection failed — can't determine, assume valid
        return True
    except Exception as e:
        logger.debug(f"SMTP probe error for {email}: {e}")
        return True  # Assume valid on error to avoid losing leads


def verify_email(email: str, deep_check: bool = True) -> dict:
    """
    Full email verification pipeline.
    Returns dict with: valid (bool), reason (str), checks (dict).
    """
    email = email.strip().lower()
    result = {
        "email": email,
        "valid": False,
        "reason": "",
        "checks": {
            "format": False,
            "disposable": True,
            "mx_record": False,
            "smtp_exists": None,
        },
    }

    # 1. Format check
    if not is_valid_format(email):
        result["reason"] = "Invalid email format"
        return result
    result["checks"]["format"] = True

    # 2. Disposable check
    if is_disposable(email):
        result["reason"] = "Disposable email domain"
        result["checks"]["disposable"] = True
        return result
    result["checks"]["disposable"] = False

    # 3. Domain / MX check
    domain = email.split("@")[1]
    if not has_mx_record(domain):
        result["reason"] = f"No MX records for domain: {domain}"
        return result
    result["checks"]["mx_record"] = True

    # 4. SMTP probe (optional, can be slow)
    if deep_check:
        exists = smtp_probe(email)
        result["checks"]["smtp_exists"] = exists
        if not exists:
            result["reason"] = "SMTP server rejected the address"
            return result

    result["valid"] = True
    result["reason"] = "All checks passed"
    return result


def batch_verify(emails: list, deep_check: bool = False) -> list:
    """
    Verify a list of emails. Returns list of results.
    Deep check is off by default for speed (MX check is usually enough).
    """
    results = []
    for email in emails:
        try:
            r = verify_email(email, deep_check=deep_check)
            results.append(r)
        except Exception as e:
            results.append({
                "email": email,
                "valid": False,
                "reason": f"Verification error: {e}",
                "checks": {},
            })
    return results
