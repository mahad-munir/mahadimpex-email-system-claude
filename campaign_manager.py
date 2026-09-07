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


def step_find_leads(min_leads_threshold: int = None):
    """Step 2: Discover new leads if we're running low."""
    if min_leads_threshold is None:
        min_leads_threshold = max(5, get_remaining_today())

    logger.info("\n" + "="*55)
    logger.info("  STEP 2: Lead Discovery & Quality Filter")
    logger.info("="*55)

    # Purge any blacklisted department emails or duplicate domains first
    db.clean_database()

    new_leads_count = db.get_leads_by_status("new")
    logger.info(f"  Available verified leads: {new_leads_count}")

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


def step_send_cold_intros(sender: EmailSender, account: dict = None, max_count: int = None):
    """Step 3: Send cold intro emails to new leads."""
    acc_name = sender.sender_name
    acc_email = sender.sender_email

    logger.info("\n" + "="*55)
    logger.info(f"  STEP 3: Sending Cold Intros for {acc_name} <{acc_email}>")
    logger.info("="*55)

    remaining = get_remaining_today(account)
    if max_count:
        remaining = min(remaining, max_count)

    if remaining <= 0:
        logger.info(f"  No sending capacity remaining today for {acc_email}")
        return 0

    # Allocate 100% to cold intros if follow-ups are disabled, otherwise 60/40 split
    from config import MAX_FOLLOWUPS
    cold_capacity = remaining if MAX_FOLLOWUPS == 0 else max(1, int(remaining * 0.6))

    leads = db.get_leads_for_emailing(limit=cold_capacity, email_type="cold_intro")
    if not leads:
        logger.info("  No new leads to email")
        return 0

    logger.info(f"  Generating & sending {len(leads)} cold intros as {acc_name}...")
    sent = 0
    bounces = 0

    for lead in leads:
        # Check remaining capacity
        if get_remaining_today(account) <= 0:
            logger.info(f"  Daily limit reached for {acc_email} — stopping")
            break

        # Generate personalized email with account persona and signature
        email_data = generate_email(lead, email_type="cold_intro", account=account)
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

    logger.info(f"  Cold intros sent for {acc_name}: {sent}, bounces: {bounces}")
    return sent


def step_send_followups(sender: EmailSender):
    """Step 4: Send follow-up emails to leads that haven't replied."""
    from config import MAX_FOLLOWUPS
    if MAX_FOLLOWUPS <= 0:
        return 0

    logger.info("\n" + "="*55)
    logger.info("  STEP 4: Sending Follow-Up Emails")
    logger.info("="*55)

    remaining = get_remaining_today(sender.account)
    if remaining <= 0:
        logger.info("  No sending capacity remaining today")
        return 0

    total_sent = 0

    for followup_num in range(1, MAX_FOLLOWUPS + 1):
        if get_remaining_today(sender.account) <= 0:
            break

        email_type = f"followup_{followup_num}"
        leads = db.get_leads_for_emailing(
            limit=min(5, get_remaining_today(sender.account)),
            email_type=email_type,
        )

        if not leads:
            continue

        logger.info(f"  Follow-up #{followup_num}: {len(leads)} leads ready")

        for lead in leads:
            if get_remaining_today(sender.account) <= 0:
                break

            prev_emails = db.get_emails_for_lead(lead["id"])
            prev_subject = prev_emails[0]["subject"] if prev_emails else ""

            email_data = generate_email(
                lead,
                email_type=email_type,
                previous_subject=prev_subject,
                account=sender.account,
            )
            if not email_data["success"]:
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
            logger.info(f"  Pausing {delay:.0f}s...")
            time.sleep(delay)

    logger.info(f"  Follow-ups sent: {total_sent}")
    return total_sent


def run_daily_campaign():
    """
    Execute the full daily campaign cycle across all configured sender accounts.
    This is the main entry point for automated runs.
    """
    _setup_logging()
    start_time = datetime.now()

    logger.info("\n" + "#"*55)
    logger.info(f"  MAHAD IMPEX — MULTI-ACCOUNT DAILY CAMPAIGN")
    logger.info(f"  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("#"*55)

    from config import ACCOUNTS, MAX_FOLLOWUPS

    # Pre-flight check across all accounts
    total_remaining = get_remaining_today()
    logger.info(f"\n  Total Senders:    {len(ACCOUNTS)}")
    logger.info(f"  Total Remaining:  {total_remaining} emails today")

    if total_remaining <= 0:
        logger.info("\n  All sender daily limits reached — not sending today")
        db.add_daily_log("campaign_skipped", "All accounts at limit")
        return

    try:
        # Step 1: Check inboxes across all accounts for replies/bounces
        inbox = step_check_inbox()

        # Step 2: Ensure sufficient verified leads are in database
        step_find_leads(min_leads_threshold=max(10, total_remaining))

        total_cold_sent = 0
        total_followup_sent = 0

        # Step 3: Run sending cycle for each account in sequence
        for account in ACCOUNTS:
            acc_name = account["name"]
            acc_email = account["email"]
            logger.info(f"\n>>> Starting outreach for: {acc_name} <{acc_email}>")

            can_send, reason = should_send_today(account)
            if not can_send:
                logger.info(f"  Skipping {acc_email}: {reason}")
                continue

            sender = EmailSender(account)
            try:
                cold_sent = step_send_cold_intros(sender, account=account)
                followup_sent = step_send_followups(sender) if MAX_FOLLOWUPS > 0 else 0

                total_cold_sent += cold_sent
                total_followup_sent += followup_sent

                log_today_metrics(
                    emails_sent=cold_sent + followup_sent,
                    bounces=0,
                    notes=f"Sender: {acc_email}, Cold: {cold_sent}, Followups: {followup_sent}",
                    account=account,
                )
            finally:
                sender.close()

        elapsed = (datetime.now() - start_time).total_seconds()
        total_sent = total_cold_sent + total_followup_sent

        logger.info("\n" + "#"*55)
        logger.info(f"  DAILY RUN COMPLETE")
        logger.info(f"  Total emails sent: {total_sent}")
        logger.info(f"  Cold intros:       {total_cold_sent}")
        logger.info(f"  Follow-ups:        {total_followup_sent}")
        logger.info(f"  Replies today:     {inbox.get('replies', 0)}")
        logger.info(f"  Bounces today:     {inbox.get('bounces', 0)}")
        logger.info(f"  Duration:          {elapsed:.0f}s")
        logger.info("#"*55 + "\n")

        db.add_daily_log("campaign_completed",
                         f"Sent {total_sent} across {len(ACCOUNTS)} accounts")

    except Exception as e:
        logger.error(f"\nCampaign run failed: {e}", exc_info=True)
        db.add_daily_log("campaign_error", str(e))


if __name__ == "__main__":
    run_daily_campaign()
