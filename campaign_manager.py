"""
Mahad Impex Email Marketing System — Campaign Manager
Main orchestrator that ties all modules together for automated daily runs.
"""

import logging
import time
import random
from datetime import datetime, date

import database as db
from lead_finder import run_lead_discovery
from email_generator import generate_email
from email_sender import EmailSender, check_for_replies_and_bounces
from warmup_manager import (
    get_daily_limit, get_remaining_today, should_send_today,
    log_today_metrics, get_warmup_status,
)
from config import (
    TARGET_MARKETS, PRODUCT_LINES,
    FOLLOWUP_DELAYS_DAYS, MAX_FOLLOWUPS,
    MIN_DELAY_SECONDS, MAX_DELAY_SECONDS,
    LOG_DIR,
)

logger = logging.getLogger(__name__)


def _setup_logging():
    """Configure logging for the daily run."""
    today = date.today().isoformat()
    log_file = LOG_DIR / f"campaign_{today}.log"

    # File handler
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers on repeated runs
    root.handlers = [fh, ch]


def step_check_inbox():
    """Step 1: Check for replies, bounces, unsubscribes."""
    logger.info("\n" + "="*55)
    logger.info("  STEP 1: Checking inbox for replies & bounces")
    logger.info("="*55)

    try:
        result = check_for_replies_and_bounces()
        logger.info(
            f"  Replies: {result['replies']} | "
            f"Bounces: {result['bounces']} | "
            f"Unsubscribes: {result['unsubscribes']}"
        )
        return result
    except Exception as e:
        logger.error(f"  Inbox check failed: {e}")
        return {"replies": 0, "bounces": 0, "unsubscribes": 0}


def step_find_leads(min_leads_threshold: int = 50):
    """Step 2: Discover new leads if we're running low."""
    logger.info("\n" + "="*55)
    logger.info("  STEP 2: Lead Discovery")
    logger.info("="*55)

    new_leads_count = db.get_leads_by_status("new")
    logger.info(f"  Available new leads: {new_leads_count}")

    if new_leads_count >= min_leads_threshold:
        logger.info(f"  Sufficient leads available — skipping discovery")
        return 0

    # Find leads for top priority markets/products
    leads_needed = min_leads_threshold - new_leads_count
    leads_per_combo = max(3, leads_needed // 6)  # Spread across combos

    logger.info(f"  Need ~{leads_needed} more leads, searching...")

    try:
        new = run_lead_discovery(
            max_leads_per_combo=leads_per_combo,
            markets=TARGET_MARKETS[:4],    # Top 4 markets
            products=PRODUCT_LINES[:2],     # Top 2 products
        )
        logger.info(f"  Discovered {new} new leads")
        return new
    except Exception as e:
        logger.error(f"  Lead discovery failed: {e}")
        return 0


def step_send_cold_intros(sender: EmailSender, max_count: int = None):
    """Step 3: Send cold intro emails to new leads."""
    logger.info("\n" + "="*55)
    logger.info("  STEP 3: Sending Cold Intro Emails")
    logger.info("="*55)

    remaining = get_remaining_today()
    if max_count:
        remaining = min(remaining, max_count)

    if remaining <= 0:
        logger.info("  No sending capacity remaining today")
        return 0

    # Allocate 60% of capacity to cold intros, 40% to follow-ups
    cold_capacity = max(1, int(remaining * 0.6))

    leads = db.get_leads_for_emailing(limit=cold_capacity, email_type="cold_intro")
    if not leads:
        logger.info("  No new leads to email")
        return 0

    logger.info(f"  Generating & sending {len(leads)} cold intros...")
    sent = 0
    bounces = 0

    for lead in leads:
        # Check remaining capacity
        if get_remaining_today() <= 0:
            logger.info("  Daily limit reached — stopping")
            break

        # Generate personalized email
        email_data = generate_email(lead, email_type="cold_intro")
        if not email_data["success"]:
            logger.warning(f"  Skipped {lead['email']} — generation failed")
            continue

        # Check spam score — skip if too risky
        spam_score = email_data["spam_check"].get("total_score", 0)
        if spam_score > 30:
            logger.warning(
                f"  Skipped {lead['email']} — spam score too high ({spam_score})"
            )
            continue

        # Send
        result = sender.send_email(
            to_email=lead["email"],
            subject=email_data["subject"],
            body=email_data["body"],
            lead_id=lead["id"],
            email_type="cold_intro",
        )

        if result["success"]:
            sent += 1
        elif "refused" in result.get("error", "").lower():
            bounces += 1

        # Human-like delay
        delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
        logger.info(f"  Pausing {delay:.0f}s...")
        time.sleep(delay)

    logger.info(f"  Cold intros sent: {sent}, bounces: {bounces}")
    return sent


def step_send_followups(sender: EmailSender):
    """Step 4: Send follow-up emails to leads that haven't replied."""
    logger.info("\n" + "="*55)
    logger.info("  STEP 4: Sending Follow-Up Emails")
    logger.info("="*55)

    remaining = get_remaining_today()
    if remaining <= 0:
        logger.info("  No sending capacity remaining today")
        return 0

    total_sent = 0

    for followup_num in range(1, MAX_FOLLOWUPS + 1):
        if get_remaining_today() <= 0:
            break

        email_type = f"followup_{followup_num}"
        leads = db.get_leads_for_emailing(
            limit=min(5, get_remaining_today()),
            email_type=email_type,
        )

        if not leads:
            continue

        logger.info(f"  Follow-up #{followup_num}: {len(leads)} leads ready")

        for lead in leads:
            if get_remaining_today() <= 0:
                break

            # Get the previous email subject for context
            conn = db.get_connection()
            prev = conn.execute(
                """SELECT subject FROM emails_sent
                   WHERE lead_id = ? ORDER BY sent_at DESC LIMIT 1""",
                (lead["id"],)
            ).fetchone()
            conn.close()
            prev_subject = prev["subject"] if prev else ""

            # Generate follow-up
            email_data = generate_email(
                lead, email_type=email_type,
                previous_subject=prev_subject,
            )

            if not email_data["success"]:
                continue

            if email_data["spam_check"].get("total_score", 0) > 30:
                continue

            result = sender.send_email(
                to_email=lead["email"],
                subject=email_data["subject"],
                body=email_data["body"],
                lead_id=lead["id"],
                email_type=email_type,
            )

            if result["success"]:
                total_sent += 1

            delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
            time.sleep(delay)

    logger.info(f"  Follow-ups sent: {total_sent}")
    return total_sent


def run_daily_campaign():
    """
    Execute the full daily campaign cycle.
    This is the main entry point for automated runs.
    """
    _setup_logging()
    start_time = datetime.now()

    logger.info("\n" + "#"*55)
    logger.info(f"  MAHAD IMPEX — DAILY CAMPAIGN RUN")
    logger.info(f"  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("#"*55)

    # Pre-flight check
    can_send, reason = should_send_today()
    warmup = get_warmup_status()

    logger.info(f"\n  Phase:      {warmup['phase']} (Week {warmup['week']})")
    logger.info(f"  Limit:      {warmup['daily_limit']} emails/day")
    logger.info(f"  Health:     {warmup['health']}")
    logger.info(f"  Can send:   {reason}")

    if not can_send:
        logger.info("\n  Campaign paused — not sending today")
        db.add_daily_log("campaign_skipped", reason)
        return

    # Initialize sender
    sender = EmailSender()

    try:
        # Step 1: Check inbox
        inbox = step_check_inbox()

        # Step 2: Find leads
        step_find_leads()

        # Step 3: Send cold intros
        cold_sent = step_send_cold_intros(sender)

        # Step 4: Send follow-ups
        followup_sent = step_send_followups(sender)

        # Log daily metrics
        total_sent = cold_sent + followup_sent
        log_today_metrics(
            emails_sent=total_sent,
            bounces=inbox.get("bounces", 0),
            notes=f"Cold: {cold_sent}, Followups: {followup_sent}",
        )

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("\n" + "#"*55)
        logger.info(f"  DAILY RUN COMPLETE")
        logger.info(f"  Emails sent:     {total_sent}")
        logger.info(f"  Cold intros:     {cold_sent}")
        logger.info(f"  Follow-ups:      {followup_sent}")
        logger.info(f"  Replies today:   {inbox.get('replies', 0)}")
        logger.info(f"  Bounces today:   {inbox.get('bounces', 0)}")
        logger.info(f"  Duration:        {elapsed:.0f}s")
        logger.info("#"*55 + "\n")

        db.add_daily_log("campaign_completed",
                         f"Sent {total_sent} (cold={cold_sent}, fu={followup_sent})")

    except Exception as e:
        logger.error(f"\nCampaign run failed: {e}", exc_info=True)
        db.add_daily_log("campaign_error", str(e))
    finally:
        sender.close()


if __name__ == "__main__":
    run_daily_campaign()
