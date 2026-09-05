"""
Mahad Impex Email Marketing System — Dashboard
Terminal-based monitoring dashboard with rich formatting.
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
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box

import database as db
from warmup_manager import get_warmup_status

console = Console()
logger = logging.getLogger(__name__)


def show_dashboard():
    """Display the full monitoring dashboard."""
    stats = db.get_dashboard_stats()
    warmup = get_warmup_status()

    console.clear()

    # Header
    header = Text()
    header.append("\n  MAHAD IMPEX ", style="bold white on blue")
    header.append(" Email Marketing Dashboard ", style="bold white on dark_blue")
    header.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}", style="dim")
    console.print(header)
    console.print()

    # ── Warm-Up Status Panel ──
    warmup_text = (
        f"{warmup['phase_emoji']} Phase: {warmup['phase']} (Week {warmup['week']})\n"
        f"   Domain age: {warmup['domain_age_days']} days\n"
        f"   Daily limit: {warmup['daily_limit']} emails\n"
        f"   Sent today: {warmup['sent_today']} / {warmup['daily_limit']}\n"
        f"   Remaining: {warmup['remaining_today']}\n"
        f"   Health: {warmup['health']}\n"
        f"   Bounce rate (7d): {warmup['bounce_rate_7d']:.1%}"
    )
    console.print(Panel(warmup_text, title="🔥 Domain Warm-Up",
                         border_style="yellow", width=60))
    console.print()

    # ── Lead Statistics ──
    leads_table = Table(title="📋 Lead Statistics", box=box.ROUNDED,
                        show_header=True, header_style="bold cyan", width=60)
    leads_table.add_column("Metric", style="white", width=30)
    leads_table.add_column("Count", justify="right", style="green", width=15)

    leads_table.add_row("Total Leads", str(stats["total_leads"]))
    leads_table.add_row("New (not yet emailed)", str(stats["new_leads"]))
    leads_table.add_row("Emailed", str(stats["emailed"]))
    leads_table.add_row("Replied ✓", f"[bold green]{stats['replied']}[/]")
    leads_table.add_row("Bounced", f"[red]{stats['bounced']}[/]")
    leads_table.add_row("Unsubscribed", str(stats["unsubscribed"]))

    console.print(leads_table)
    console.print()

    # ── Sending Statistics ──
    send_table = Table(title="📤 Sending Statistics", box=box.ROUNDED,
                       show_header=True, header_style="bold cyan", width=60)
    send_table.add_column("Period", style="white", width=30)
    send_table.add_column("Emails Sent", justify="right", style="yellow", width=15)

    send_table.add_row("Today", str(stats["sent_today"]))
    send_table.add_row("This week", str(stats["sent_week"]))
    send_table.add_row("This month", str(stats["sent_month"]))
    send_table.add_row("All time", str(stats["sent_total"]))

    console.print(send_table)
    console.print()

    # ── Country Breakdown ──
    if stats["by_country"]:
        country_table = Table(title="🌍 Leads by Country", box=box.ROUNDED,
                              show_header=True, header_style="bold cyan", width=60)
        country_table.add_column("Country", style="white", width=30)
        country_table.add_column("Leads", justify="right", style="magenta", width=15)

        for country, count in stats["by_country"].items():
            country_table.add_row(country, str(count))

        console.print(country_table)
        console.print()

    # ── Warm-Up Schedule ──
    schedule_table = Table(title="📅 Warm-Up Schedule", box=box.ROUNDED,
                           show_header=True, header_style="bold cyan", width=60)
    schedule_table.add_column("Week", style="white", width=15)
    schedule_table.add_column("Daily Limit", justify="right", width=15)
    schedule_table.add_column("Status", width=20)

    for wk, limit in sorted(warmup["warmup_schedule"].items()):
        if wk < warmup["week"]:
            status = "[green]✓ Complete[/]"
        elif wk == warmup["week"]:
            status = "[yellow]◀ Current[/]"
        else:
            status = "[dim]Upcoming[/]"
        schedule_table.add_row(f"Week {wk}", str(limit), status)

    console.print(schedule_table)
    console.print()

    # ── Recent Activity ──
    activities = db.get_recent_activity(limit=10)
    if activities:
        activity_table = Table(title="📝 Recent Activity", box=box.ROUNDED,
                               show_header=True, header_style="bold cyan", width=60)
        activity_table.add_column("Time", style="dim", width=18)
        activity_table.add_column("Action", style="white", width=15)
        activity_table.add_column("Details", style="cyan", width=22)

        for act in activities:
            time_str = act.get("created_at", "")[:16]
            activity_table.add_row(
                time_str,
                act.get("action", ""),
                act.get("details", "")[:40],
            )

        console.print(activity_table)
        console.print()

    # Footer
    console.print(
        "[dim]Commands: python main.py run | find-leads | "
        "send-test | warmup-status | check-dns[/]"
    )
    console.print()
