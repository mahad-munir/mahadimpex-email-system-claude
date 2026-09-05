"""
Mahad Impex Email Marketing System — Anti-Spam Guard
Multi-layer content and technical checks to ensure deliverability.
"""

import re
import json
import logging
from pathlib import Path
from config import (
    DATA_DIR, MAX_SUBJECT_LENGTH, MAX_EMAIL_LINKS,
    MAX_EXCLAMATION_MARKS, INCLUDE_UNSUBSCRIBE,
    INCLUDE_PHYSICAL_ADDRESS, COMPANY_ADDRESS, COMPANY_WEBSITE,
    SENDER_EMAIL,
)

logger = logging.getLogger(__name__)

# Load spam words database
_spam_words_path = DATA_DIR / "spam_words.json"
_spam_data = {}
if _spam_words_path.exists():
    with open(_spam_words_path, "r") as f:
        _spam_data = json.load(f)

HIGH_RISK_WORDS = set(w.lower() for w in _spam_data.get("high_risk", []))
MEDIUM_RISK_WORDS = set(w.lower() for w in _spam_data.get("medium_risk", []))


def check_spam_words(text: str) -> dict:
    """
    Scan text for spam trigger words.
    Returns dict with found words and risk score.
    """
    text_lower = text.lower()
    found_high = []
    found_medium = []

    for word in HIGH_RISK_WORDS:
        # Match whole words/phrases only
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text_lower):
            found_high.append(word)

    for word in MEDIUM_RISK_WORDS:
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, text_lower):
            found_medium.append(word)

    score = len(found_high) * 10 + len(found_medium) * 3
    return {
        "high_risk": found_high,
        "medium_risk": found_medium,
        "spam_score": score,
    }


def check_subject_line(subject: str) -> dict:
    """Validate subject line against spam heuristics."""
    issues = []
    score = 0

    # Length check
    if len(subject) > MAX_SUBJECT_LENGTH:
        issues.append(f"Subject too long ({len(subject)} chars, max {MAX_SUBJECT_LENGTH})")
        score += 5

    if len(subject) < 10:
        issues.append("Subject too short (under 10 chars)")
        score += 5

    # ALL CAPS check
    words = subject.split()
    caps_words = [w for w in words if w.isupper() and len(w) > 2]
    if len(caps_words) > 0:
        issues.append(f"ALL CAPS words in subject: {caps_words}")
        score += 15

    # Excessive punctuation
    if subject.count("!") > 1:
        issues.append("Multiple exclamation marks in subject")
        score += 10

    if subject.count("?") > 2:
        issues.append("Too many question marks in subject")
        score += 5

    if "!!!" in subject or "???" in subject:
        issues.append("Excessive punctuation in subject")
        score += 15

    # Starts with "Re:" or "Fwd:" artificially
    if subject.lower().startswith(("re:", "fwd:", "fw:")):
        # This is a common spam trick — but we do use it legitimately for follow-ups
        # Only flag if it's a cold intro
        pass

    # Spam words in subject
    spam_check = check_spam_words(subject)
    if spam_check["high_risk"]:
        issues.append(f"Spam trigger words in subject: {spam_check['high_risk']}")
        score += spam_check["spam_score"]

    return {"issues": issues, "score": score}


def check_body(body: str) -> dict:
    """Validate email body against spam heuristics."""
    issues = []
    score = 0

    # Spam words
    spam_check = check_spam_words(body)
    if spam_check["high_risk"]:
        issues.append(f"High-risk spam words: {spam_check['high_risk'][:5]}")
        score += spam_check["spam_score"]
    if spam_check["medium_risk"]:
        # Medium risk words are okay in moderation
        if len(spam_check["medium_risk"]) > 3:
            issues.append(f"Many medium-risk words: {spam_check['medium_risk'][:5]}")
            score += 5

    # Exclamation marks
    excl_count = body.count("!")
    if excl_count > MAX_EXCLAMATION_MARKS:
        issues.append(f"Too many exclamation marks ({excl_count})")
        score += excl_count * 3

    # ALL CAPS words (excluding short words and common acronyms)
    words = body.split()
    caps_words = [w for w in words if w.isupper() and len(w) > 3
                  and w not in ("OEKO-TEX", "GOTS", "ISO", "MOQ", "USA",
                                "UK", "EU", "GSM", "UAE", "B2B")]
    if len(caps_words) > 2:
        issues.append(f"Too many ALL CAPS words: {caps_words[:3]}")
        score += len(caps_words) * 5

    # Link count
    url_pattern = re.compile(r"https?://\S+")
    links = url_pattern.findall(body)
    if len(links) > MAX_EMAIL_LINKS:
        issues.append(f"Too many links ({len(links)}, max {MAX_EMAIL_LINKS})")
        score += (len(links) - MAX_EMAIL_LINKS) * 10

    # Dollar signs (price spam)
    if body.count("$") > 2:
        issues.append("Multiple dollar signs detected")
        score += 5

    # Unsubscribe check
    if INCLUDE_UNSUBSCRIBE:
        has_unsub = any(phrase in body.lower() for phrase in
                        ["unsubscribe", "opt out", "opt-out",
                         "remove me", "stop receiving"])
        if not has_unsub:
            issues.append("Missing unsubscribe mechanism")
            score += 15

    # Physical address check
    if INCLUDE_PHYSICAL_ADDRESS:
        if COMPANY_ADDRESS.lower() not in body.lower():
            # Check for any address-like pattern
            has_address = any(word in body.lower() for word in
                              ["faisalabad", "pakistan", "punjab"])
            if not has_address:
                issues.append("Missing physical business address")
                score += 10

    # Body length
    if len(body) < 100:
        issues.append("Email body too short (under 100 chars)")
        score += 5
    elif len(body) > 3000:
        issues.append("Email body very long (over 3000 chars)")
        score += 5

    # Image-heavy content (shouldn't have images in plain text)
    if "<img" in body.lower():
        issues.append("Contains image tags (use plain text)")
        score += 10

    return {"issues": issues, "score": score}


def check_email(subject: str, body: str) -> dict:
    """
    Run full spam check on an email.
    Returns verdict: pass / warn / fail with details.
    """
    subject_result = check_subject_line(subject)
    body_result = check_body(body)

    total_score = subject_result["score"] + body_result["score"]
    all_issues = subject_result["issues"] + body_result["issues"]

    if total_score <= 10:
        verdict = "pass"
    elif total_score <= 30:
        verdict = "warn"
    else:
        verdict = "fail"

    return {
        "verdict": verdict,
        "total_score": total_score,
        "issues": all_issues,
        "subject_score": subject_result["score"],
        "body_score": body_result["score"],
    }


def get_unsubscribe_footer() -> str:
    """Generate the unsubscribe / compliance footer."""
    footer = (
        f"\n\n---\n"
        f"{COMPANY_ADDRESS}\n"
        f"If you'd prefer not to hear from us, simply reply with "
        f"\"unsubscribe\" and we'll remove you from our list right away."
    )
    return footer


def sanitize_email_content(subject: str, body: str) -> tuple:
    """
    Attempt to fix common spam issues automatically.
    Returns (cleaned_subject, cleaned_body).
    """
    # Fix subject
    clean_subject = subject.strip()
    # Remove multiple exclamation marks
    while "!!" in clean_subject:
        clean_subject = clean_subject.replace("!!", "!")
    # Truncate if too long
    if len(clean_subject) > MAX_SUBJECT_LENGTH:
        clean_subject = clean_subject[:MAX_SUBJECT_LENGTH - 3] + "..."

    # Fix body
    clean_body = body.strip()
    # Remove excessive exclamation marks
    while "!!" in clean_body:
        clean_body = clean_body.replace("!!", "!")

    # Ensure unsubscribe footer
    has_unsub = any(phrase in clean_body.lower() for phrase in
                    ["unsubscribe", "opt out", "opt-out"])
    if not has_unsub:
        clean_body += get_unsubscribe_footer()

    return clean_subject, clean_body
