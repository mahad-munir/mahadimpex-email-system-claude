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
    GEMINI_API_KEY, SENDER_EMAIL, COMPANY_WEBSITE, ACCOUNTS,
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
    """Send a test email to verify SMTP and IMAP for active accounts."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from email_sender import EmailSender

    filter_account = None
    custom_to_email = None

    for arg in sys.argv[2:]:
        arg_l = arg.lower()
        if "munir" in arg_l and "aliyan" not in arg_l:
            filter_account = "munir"
        elif "aliyan" in arg_l:
            filter_account = "aliyan"
        elif "@" in arg:
            custom_to_email = arg

    target_accounts = []
    for acc in ACCOUNTS:
        if filter_account == "munir":
            if acc["email"].lower().startswith("munir@") or "muhammad" in acc["name"].lower():
                target_accounts.append(acc)
        elif filter_account == "aliyan":
            if "aliyan" in acc["email"].lower() or "aliyan" in acc["name"].lower():
                target_accounts.append(acc)
        else:
            target_accounts.append(acc)

    if not target_accounts:
        print(f"\n⚠️  No matching accounts found for '{filter_account}'!\n")
        return

    for acc in target_accounts:
        to_addr = custom_to_email if custom_to_email else acc["email"]
        print(f"\n📧 Sending test email from {acc['name']} ({acc['email']}) to {to_addr}...")
        if not acc.get("password"):
            print(f"⚠️  Password missing for {acc['email']} in .env!")
            continue

        sender = EmailSender(account=acc)
        result = sender.send_test(to_email=to_addr)
        sender.close()

        if result["success"]:
            print(f"  ✓ Test email sent successfully for {acc['name']}!")
            print(f"  Check inbox at: {to_addr}")
            print(f"  Message ID: {result['message_id']}")
            print(f"  Saved to IMAP Sent folder: ✓")
        else:
            print(f"  ✗ Test email failed for {acc['name']}: {result['error']}")
    print()


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
    """Generate and preview emails for configured accounts without sending."""
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    from email_generator import generate_email

    if not GEMINI_API_KEY:
        print("\n⚠️  GEMINI_API_KEY is not set in .env file!\n")
        return

    sample_lead = {
        "id": 0,
        "email": "buyer@example.com",
        "company_name": "Example Home Textiles Ltd",
        "first_name": "James",
        "country": "United Kingdom",
        "country_code": "UK",
        "product_interest": "Bed Linen & Bed Sets",
    }

    filter_account = None
    for arg in sys.argv[2:]:
        arg_l = arg.lower()
        if "munir" in arg_l and "aliyan" not in arg_l:
            filter_account = "munir"
        elif "aliyan" in arg_l:
            filter_account = "aliyan"

    target_accounts = []
    for acc in ACCOUNTS:
        if filter_account == "munir":
            if acc["email"].lower().startswith("munir@") or "muhammad" in acc["name"].lower():
                target_accounts.append(acc)
        elif filter_account == "aliyan":
            if "aliyan" in acc["email"].lower() or "aliyan" in acc["name"].lower():
                target_accounts.append(acc)
        else:
            target_accounts.append(acc)

    for acc in target_accounts:
        print(f"\n📝 Generating sample email for {acc['name']} ({acc['title']})...\n")
        result = generate_email(sample_lead, email_type="cold_intro", account=acc)

        if result["success"]:
            print(f"{'='*60}")
            print(f"  PREVIEW FOR: {acc['name']} — {acc['title']}")
            print(f"  FROM:        {acc['name']} <{acc['email']}>")
            print(f"  SUBJECT:     {result['subject']}")
            print(f"{'='*60}")
            print(result["body"])
            print(f"{'='*60}")
            print(f"  Spam Score: {result['spam_check'].get('total_score', 'N/A')}")
            print(f"  Verdict:    {result['spam_check'].get('verdict', 'N/A')}")
            if result["spam_check"].get("issues"):
                print(f"  Issues:     {result['spam_check']['issues']}")
            print(f"{'='*60}\n")
        else:
            print(f"\n✗ Generation failed for {acc['name']}: {result.get('error', 'unknown')}\n")


def cmd_stats():
    """Quick stats overview with per-sender breakdown."""
    import database as db
    stats = db.get_dashboard_stats()

    print(f"\n{'='*55}")
    print(f"  Quick Stats — Mahad Impex Outreach System")
    print(f"{'='*55}")
    print(f"  Total Leads in Database: {stats['total_leads']}")
    print(f"  New (Uncontacted):       {stats['new_leads']}")
    print(f"  Total Contacted:         {stats['emailed']}")
    print(f"  Replies Received:        {stats['replied']}")
    print(f"  Bounced:                 {stats['bounced']}")
    print(f"  Bounce Rate:             {stats['bounce_rate']:.1%}")
    print(f"{'-'*55}")
    print(f"  Today's Sends (Combined): {stats['sent_today']}")
    from warmup_manager import get_daily_limit
    for acc in ACCOUNTS:
        sent_acc_today = db.get_emails_sent_today_by_sender(acc["email"])
        lim = get_daily_limit(acc)
        type_str = "Warmed up" if acc.get("is_warmed_up") else "Warmup"
        print(f"    • {acc['name']} ({acc['email']}): {sent_acc_today}/{lim} sent today [{type_str}]")
    print(f"  Sent This Week:           {stats['sent_week']}")
    print(f"{'='*55}\n")


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
        from_acc = em.get("from_email") or "Unknown sender"
        print(f"\n[{idx}] To:   {em['to_email']} ({company}, {country})")
        print(f"    From: {from_acc}")
        print(f"    Date: {em.get('sent_at', '')}")
        print(f"    Type: {em.get('email_type', '')}")
        print(f"    Subj: {em.get('subject', '')}")
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
║  Accounts Configured:                                ║
║    1. Muhammad Munir (Marketing Director)            ║
║       munir@mahadimpex.com [Warmed up: ~45/day]      ║
║    2. Aliyan Munir (Head of International Sourcing)  ║
║       aliyanmunir@mahadimpex.com [Warmup schedule]   ║
║                                                      ║
║  Commands:                                           ║
║    python main.py run           Full daily cycle     ║
║    python main.py find-leads    Discover new leads   ║
║    python main.py dashboard     View dashboard       ║
║    python main.py sent          View sent emails     ║
║    python main.py preview       Preview AI emails    ║
║    python main.py send-test     Test email delivery  ║
║    python main.py check-dns     Check SPF/DKIM/DMARC ║
║    python main.py warmup-status Warm-up progress     ║
║    python main.py stats         Quick statistics     ║
║    python main.py help          This help message    ║
║                                                      ║
║  Options for preview & send-test:                    ║
║    python main.py preview munir                      ║
║    python main.py preview aliyan                     ║
║    python main.py send-test munir                    ║
║    python main.py send-test aliyan                   ║
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
