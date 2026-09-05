"""
Mahad Impex Email Marketing System — Main CLI Entry Point
Run all operations from the command line.
"""

import sys
import os
import logging

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import dns.resolver

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    GEMINI_API_KEY, SENDER_EMAIL, COMPANY_WEBSITE,
)


def cmd_run():
    """Run the full daily campaign cycle."""
    from campaign_manager import run_daily_campaign
    run_daily_campaign()


def cmd_find_leads():
    """Discover new leads only."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from lead_finder import run_lead_discovery
    print("\n🔍 Starting lead discovery...\n")
    total = run_lead_discovery(max_leads_per_combo=10)
    print(f"\n✓ Found {total} new leads\n")


def cmd_dashboard():
    """Show the monitoring dashboard."""
    from dashboard import show_dashboard
    show_dashboard()


def cmd_send_test():
    """Send a test email to yourself."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from email_sender import EmailSender

    if not SMTP_PASSWORD:
        print("\n⚠️  SMTP_PASSWORD is not set in .env file!")
        print("   Edit .env and add your email password.\n")
        return

    print(f"\n📧 Sending test email to {SENDER_EMAIL}...")
    sender = EmailSender()
    result = sender.send_test()
    sender.close()

    if result["success"]:
        print(f"\n✓ Test email sent successfully!")
        print(f"  Check your inbox at {SENDER_EMAIL}")
        print(f"  Message ID: {result['message_id']}")
        print(f"\n  Next step: Check if it landed in Inbox (not Spam)")
        print(f"  Also test at: https://www.mail-tester.com\n")
    else:
        print(f"\n✗ Test email failed: {result['error']}")
        print(f"  Check your SMTP settings in .env\n")


def cmd_check_dns():
    """Verify DNS records (SPF, DKIM, DMARC) for the domain."""
    domain = "mahadimpex.com"
    print(f"\n🔍 Checking DNS records for {domain}...\n")

    # SPF
    print("  SPF Record:")
    try:
        answers = dns.resolver.resolve(domain, "TXT")
        spf_found = False
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            if "v=spf1" in txt:
                print(f"    ✓ Found: {txt}")
                spf_found = True
        if not spf_found:
            print(f"    ✗ No SPF record found!")
            print(f"    → Add a TXT record: v=spf1 a mx ~all")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    print()

    # DKIM
    print("  DKIM Record:")
    dkim_selectors = ["default", "mail", "dkim", "selector1", "selector2"]
    dkim_found = False
    for selector in dkim_selectors:
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"
            answers = dns.resolver.resolve(dkim_domain, "TXT")
            for rdata in answers:
                txt = rdata.to_text().strip('"')
                print(f"    ✓ Found ({selector}): {txt[:80]}...")
                dkim_found = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            continue
        except Exception:
            continue
    if not dkim_found:
        print(f"    ⚠ No DKIM record found (checked: {', '.join(dkim_selectors)})")
        print(f"    → Check cPanel > Email Deliverability for DKIM setup")

    print()

    # DMARC
    print("  DMARC Record:")
    try:
        answers = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        for rdata in answers:
            txt = rdata.to_text().strip('"')
            print(f"    ✓ Found: {txt}")
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        print(f"    ✗ No DMARC record found!")
        print(f"    → Add TXT record for _dmarc.{domain}:")
        print(f"      v=DMARC1; p=none; rua=mailto:dmarc@{domain}")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    print()

    # MX
    print("  MX Records:")
    try:
        answers = dns.resolver.resolve(domain, "MX")
        for rdata in answers:
            print(f"    ✓ {rdata.preference} {rdata.exchange}")
    except Exception as e:
        print(f"    ✗ Error: {e}")

    print(f"\n  For a full email score test, send an email to:")
    print(f"  https://www.mail-tester.com\n")


def cmd_warmup_status():
    """Show detailed warm-up status."""
    from warmup_manager import print_warmup_report
    print_warmup_report()


def cmd_generate_preview():
    """Generate and preview an email without sending."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from email_generator import generate_email

    if not GEMINI_API_KEY:
        print("\n⚠️  GEMINI_API_KEY is not set in .env file!\n")
        return

    # Create a sample lead
    sample_lead = {
        "id": 0,
        "email": "buyer@example.com",
        "company_name": "Example Home Textiles Ltd",
        "first_name": "James",
        "country": "United Kingdom",
        "country_code": "UK",
        "product_interest": "Bed Linen & Bed Sets",
    }

    print("\n📝 Generating sample email with AI...\n")
    result = generate_email(sample_lead, email_type="cold_intro")

    if result["success"]:
        print(f"{'='*55}")
        print(f"  SUBJECT: {result['subject']}")
        print(f"{'='*55}")
        print(result["body"])
        print(f"{'='*55}")
        print(f"  Spam Score: {result['spam_check'].get('total_score', 'N/A')}")
        print(f"  Verdict:    {result['spam_check'].get('verdict', 'N/A')}")
        if result["spam_check"].get("issues"):
            print(f"  Issues:     {result['spam_check']['issues']}")
        print(f"{'='*55}\n")
    else:
        print(f"\n✗ Generation failed: {result.get('error', 'unknown')}\n")


def cmd_stats():
    """Quick stats overview."""
    import database as db
    stats = db.get_dashboard_stats()

    print(f"\n{'='*40}")
    print(f"  Quick Stats")
    print(f"{'='*40}")
    print(f"  Total Leads:    {stats['total_leads']}")
    print(f"  New:            {stats['new_leads']}")
    print(f"  Emailed:        {stats['emailed']}")
    print(f"  Replied:        {stats['replied']}")
    print(f"  Bounced:        {stats['bounced']}")
    print(f"  Sent Today:     {stats['sent_today']}")
    print(f"  Sent This Week: {stats['sent_week']}")
    print(f"  Bounce Rate:    {stats['bounce_rate']:.1%}")
    print(f"{'='*40}\n")


def cmd_view_emails():
    """View recent drafted and sent emails with full details."""
    import database as db
    emails = db.get_recent_sent_emails(limit=10)
    if not emails:
        print("\n📭 No emails have been sent yet.\n")
        return

    print(f"\n{'='*65}")
    print(f"  RECENT SENT EMAILS ({len(emails)})")
    print(f"{'='*65}")
    for idx, em in enumerate(emails, 1):
        company = em.get("company_name") or "Unknown Company"
        country = em.get("country") or "Unknown"
        print(f"\n[{idx}] To: {em['to_email']} ({company}, {country})")
        print(f"    Date:    {em.get('sent_at', '')}")
        print(f"    Type:    {em.get('email_type', '')}")
        print(f"    Subject: {em.get('subject', '')}")
        print(f"    Body snippet:\n    " + em.get('body', '').replace('\n', '\n    ')[:300] + "...")
        print(f"{'-'*65}")
    print()


def cmd_help():
    """Show help message."""
    print(f"""
╔══════════════════════════════════════════════════════╗
║   MAHAD IMPEX — Email Marketing System              ║
╠══════════════════════════════════════════════════════╣
║                                                      ║
║  Commands:                                           ║
║    python main.py run           Full daily cycle     ║
║    python main.py find-leads    Discover new leads   ║
║    python main.py dashboard     View dashboard       ║
║    python main.py sent          View sent emails     ║
║    python main.py preview       Preview AI email     ║
║    python main.py send-test     Test email delivery  ║
║    python main.py check-dns     Check SPF/DKIM/DMARC ║
║    python main.py warmup-status Warm-up progress     ║
║    python main.py stats         Quick statistics     ║
║    python main.py help          This help message    ║
║                                                      ║
║  Automated Daily Run:                                ║
║    python setup_scheduler.py    Setup Task Scheduler ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
""")


COMMANDS = {
    "run": cmd_run,
    "find-leads": cmd_find_leads,
    "dashboard": cmd_dashboard,
    "sent": cmd_view_emails,
    "emails": cmd_view_emails,
    "send-test": cmd_send_test,
    "check-dns": cmd_check_dns,
    "warmup-status": cmd_warmup_status,
    "preview": cmd_generate_preview,
    "stats": cmd_stats,
    "help": cmd_help,
}


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return

    command = sys.argv[1].lower()

    if command in COMMANDS:
        COMMANDS[command]()
    else:
        print(f"\n✗ Unknown command: {command}")
        cmd_help()


if __name__ == "__main__":
    main()
