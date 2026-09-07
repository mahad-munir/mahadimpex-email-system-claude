"""
Mahad Impex Email Marketing System — Warm-Up Manager
Manages domain reputation building with gradual sending limits.
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import logging
from datetime import datetime, date, timedelta
from config import (
    WARMUP_SCHEDULE, MAX_DAILY_SENDS, MAX_BOUNCE_RATE,
)
import database as db

logger = logging.getLogger(__name__)

# Domain creation date (from .env or default)
import os
from dotenv import load_dotenv
from config import BASE_DIR

load_dotenv(BASE_DIR / ".env")
_warmup_start = os.getenv("WARMUP_START_DATE", "2026-09-04")
DOMAIN_CREATED = datetime.strptime(_warmup_start, "%Y-%m-%d").date()


def get_current_week() -> int:
    """Calculate which warm-up week we're in (1-indexed)."""
    today = date.today()
    days_since = (today - DOMAIN_CREATED).days
    week = (days_since // 7) + 1
    return max(1, week)


def get_daily_limit() -> int:
    """
    Get today's sending limit based on warm-up phase and reputation.
    Automatically reduces limit if bounce rate is high.
    """
    week = get_current_week()

    # Base limit from schedule
    base_limit = WARMUP_SCHEDULE.get(week, MAX_DAILY_SENDS)
    if week > max(WARMUP_SCHEDULE.keys()):
        base_limit = MAX_DAILY_SENDS

    # Check bounce rate — reduce sending if reputation is degrading
    bounce_rate = db.get_bounce_rate(days=7)
    if bounce_rate > MAX_BOUNCE_RATE:
        # Significantly reduce volume
        adjusted = max(3, base_limit // 3)
        logger.warning(
            f"High bounce rate ({bounce_rate:.1%}) detected. "
            f"Reducing daily limit from {base_limit} to {adjusted}"
        )
        return adjusted

    if bounce_rate > MAX_BOUNCE_RATE / 2:
        # Moderate reduction
        adjusted = max(5, int(base_limit * 0.6))
        logger.warning(
            f"Elevated bounce rate ({bounce_rate:.1%}). "
            f"Reducing daily limit from {base_limit} to {adjusted}"
        )
        return adjusted

    return base_limit


def get_daily_limit(account: dict = None) -> int:
    """
    Get the allowed daily sending limit.
    If an account is already warmed up (like munir@mahadimpex.com), returns its fixed limit.
    Otherwise returns the dynamic warm-up limit based on domain age and reputation.
    """
    if account and account.get("is_warmed_up"):
        return account.get("daily_limit", 45)

    week = get_current_week()
    base_limit = WARMUP_SCHEDULE.get(week, MAX_DAILY_SENDS)
    if week > max(WARMUP_SCHEDULE.keys()):
        base_limit = MAX_DAILY_SENDS

    bounce_rate = db.get_bounce_rate(days=7)
    if bounce_rate > MAX_BOUNCE_RATE:
        return max(3, base_limit // 3)
    if bounce_rate > MAX_BOUNCE_RATE / 2:
        return max(5, int(base_limit * 0.6))

    return base_limit


def get_remaining_today(account: dict = None) -> int:
    """How many more emails can we send today for an account or in total across accounts?"""
    if account is not None:
        limit = get_daily_limit(account)
        sent = db.get_emails_sent_today_by_sender(account.get("email"))
        return max(0, limit - sent)
    else:
        from config import ACCOUNTS
        return sum(get_remaining_today(acc) for acc in ACCOUNTS)


def get_warmup_status(account: dict = None) -> dict:
    """Get comprehensive warm-up status report for an account or system."""
    from config import ACCOUNT_ALIYAN
    acc = account or ACCOUNT_ALIYAN

    week = get_current_week()
    daily_limit = get_daily_limit(acc)
    sent_today = db.get_emails_sent_today_by_sender(acc.get("email"))
    remaining = max(0, daily_limit - sent_today)
    bounce_rate = db.get_bounce_rate(days=7)
    recent_stats = db.get_warmup_stats(days=14)

    if acc.get("is_warmed_up"):
        phase = "Already Warmed Up (Full Speed)"
        phase_emoji = "🟢"
    else:
        max_week = max(WARMUP_SCHEDULE.keys())
        if week >= max_week:
            phase = "Full Operation"
            phase_emoji = "🟢"
        elif week >= max_week - 1:
            phase = "Almost There"
            phase_emoji = "🟡"
        else:
            phase = "Warming Up"
            phase_emoji = "🔶"

    # Health assessment
    if bounce_rate > MAX_BOUNCE_RATE:
        health = "⚠️  UNHEALTHY — high bounce rate, sending reduced"
    elif bounce_rate > MAX_BOUNCE_RATE / 2:
        health = "🟡 CAUTION — elevated bounce rate"
    else:
        health = "🟢 HEALTHY — reputation looks good"

    return {
        "account": acc.get("email"),
        "sender_name": acc.get("name"),
        "week": week,
        "phase": phase,
        "phase_emoji": phase_emoji,
        "daily_limit": daily_limit,
        "sent_today": sent_today,
        "remaining_today": remaining,
        "bounce_rate_7d": bounce_rate,
        "health": health,
        "domain_age_days": (date.today() - DOMAIN_CREATED).days,
        "domain_created": DOMAIN_CREATED.isoformat(),
        "warmup_schedule": WARMUP_SCHEDULE,
        "recent_stats": recent_stats,
    }


def should_send_today(account: dict = None) -> tuple:
    """
    Check if we should send emails today.
    Returns (should_send: bool, reason: str).
    """
    remaining = get_remaining_today(account)

    if remaining <= 0:
        acc_name = f" for {account.get('email')}" if account else ""
        return False, f"Daily sending limit reached{acc_name}"

    bounce_rate = db.get_bounce_rate(days=3)
    if bounce_rate > MAX_BOUNCE_RATE * 1.5:
        return False, f"Bounce rate critically high ({bounce_rate:.1%}) — pausing all sends"

    # Check if it's weekend
    from config import SEND_ON_WEEKENDS
    force = os.getenv("FORCE_SEND", "false").lower() in ("true", "1", "yes")
    if not force and not SEND_ON_WEEKENDS and date.today().weekday() >= 5:
        return False, "Weekend — sending is paused"

    return True, f"OK — {remaining} emails remaining today"


def log_today_metrics(emails_sent: int, bounces: int = 0,
                       complaints: int = 0, notes: str = "",
                       account: dict = None):
    """Log today's warm-up metrics."""
    daily_limit = get_daily_limit(account)
    db.log_warmup_day(
        emails_sent=emails_sent,
        bounces=bounces,
        complaints=complaints,
        daily_limit=daily_limit,
        notes=notes,
    )


def print_warmup_report():
    """Print a formatted warm-up status report for all active accounts."""
    from config import ACCOUNTS
    print(f"\n{'='*60}")
    print("  MAHAD IMPEX — SENDER ACCOUNTS & WARM-UP STATUS")
    print(f"{'='*60}")

    for acc in ACCOUNTS:
        st = get_warmup_status(acc)
        print(f"\n  {st['phase_emoji']} {st['sender_name']} <{st['account']}>")
        print(f"     Status:      {st['phase']}")
        print(f"     Daily Limit: {st['daily_limit']} emails/day")
        print(f"     Sent Today:  {st['sent_today']}")
        print(f"     Remaining:   {st['remaining_today']}")
        print(f"     Health:      {st['health']}")

    print(f"\n  Global Health:")
    print(f"     Bounce rate (7d): {db.get_bounce_rate(days=7):.1%}")
    print(f"     Total Senders:    {len(ACCOUNTS)}")
    total_capacity = sum(get_daily_limit(acc) for acc in ACCOUNTS)
    total_remaining = sum(get_remaining_today(acc) for acc in ACCOUNTS)
    print(f"     Total Capacity:   {total_capacity} emails/day")
    print(f"     Total Remaining:  {total_remaining} emails today")
    print(f"{'='*60}\n")
