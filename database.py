"""
Mahad Impex Email Marketing System — Database Layer
SQLite database for leads, campaigns, emails, and tracking.
"""

import sqlite3
import json
from datetime import datetime, date
from pathlib import Path
from config import DB_PATH


def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    UNIQUE NOT NULL,
            company_name    TEXT    DEFAULT '',
            contact_person  TEXT    DEFAULT '',
            first_name      TEXT    DEFAULT '',
            country         TEXT    DEFAULT '',
            country_code    TEXT    DEFAULT '',
            industry        TEXT    DEFAULT 'textiles',
            product_interest TEXT   DEFAULT '',
            source          TEXT    DEFAULT '',
            source_url      TEXT    DEFAULT '',
            relevance_score INTEGER DEFAULT 50,
            status          TEXT    DEFAULT 'new',
            emails_sent     INTEGER DEFAULT 0,
            last_emailed    TEXT    DEFAULT NULL,
            last_replied    TEXT    DEFAULT NULL,
            notes           TEXT    DEFAULT '',
            created_at      TEXT    DEFAULT (datetime('now')),
            updated_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS campaigns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            email_type      TEXT    NOT NULL DEFAULT 'cold_intro',
            target_segment  TEXT    DEFAULT '',
            target_country  TEXT    DEFAULT '',
            product_focus   TEXT    DEFAULT '',
            status          TEXT    DEFAULT 'active',
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS emails_sent (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id         INTEGER NOT NULL,
            campaign_id     INTEGER DEFAULT NULL,
            email_type      TEXT    NOT NULL DEFAULT 'cold_intro',
            subject         TEXT    NOT NULL,
            body            TEXT    NOT NULL,
            from_email      TEXT    NOT NULL,
            to_email        TEXT    NOT NULL,
            status          TEXT    DEFAULT 'sent',
            message_id      TEXT    DEFAULT '',
            sent_at         TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );

        CREATE TABLE IF NOT EXISTS email_tracking (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id        INTEGER UNIQUE NOT NULL,
            bounced         INTEGER DEFAULT 0,
            bounce_reason   TEXT    DEFAULT '',
            replied         INTEGER DEFAULT 0,
            replied_at      TEXT    DEFAULT NULL,
            unsubscribed    INTEGER DEFAULT 0,
            FOREIGN KEY (email_id) REFERENCES emails_sent(id)
        );

        CREATE TABLE IF NOT EXISTS unsubscribed (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            email           TEXT    UNIQUE NOT NULL,
            reason          TEXT    DEFAULT '',
            unsubscribed_at TEXT    DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS warmup_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date        TEXT    UNIQUE NOT NULL,
            emails_sent     INTEGER DEFAULT 0,
            bounces         INTEGER DEFAULT 0,
            complaints      INTEGER DEFAULT 0,
            daily_limit     INTEGER DEFAULT 5,
            notes           TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS daily_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date        TEXT    NOT NULL,
            action          TEXT    NOT NULL,
            details         TEXT    DEFAULT '',
            created_at      TEXT    DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_country ON leads(country_code);
        CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
        CREATE INDEX IF NOT EXISTS idx_emails_lead ON emails_sent(lead_id);
        CREATE INDEX IF NOT EXISTS idx_emails_type ON emails_sent(email_type);
        CREATE INDEX IF NOT EXISTS idx_unsub_email ON unsubscribed(email);
    """)

    conn.commit()
    conn.close()


# ── Lead Operations ──────────────────────────────────────────

def add_lead(email, company_name="", contact_person="", first_name="",
             country="", country_code="", industry="textiles",
             product_interest="", source="", source_url="",
             relevance_score=50):
    """Add a new lead. Returns lead id or None if duplicate."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO leads
               (email, company_name, contact_person, first_name, country,
                country_code, industry, product_interest, source, source_url,
                relevance_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (email.lower().strip(), company_name, contact_person, first_name,
             country, country_code, industry, product_interest, source,
             source_url, relevance_score)
        )
        conn.commit()
        return cursor.lastrowid if cursor.rowcount > 0 else None
    finally:
        conn.close()


def get_leads_for_emailing(limit=10, email_type="cold_intro"):
    """Get leads ready to receive emails."""
    conn = get_connection()
    try:
        if email_type == "cold_intro":
            # Leads that have never been emailed
            rows = conn.execute(
                """SELECT * FROM leads
                   WHERE status = 'new'
                     AND email NOT IN (SELECT email FROM unsubscribed)
                   ORDER BY relevance_score DESC, created_at ASC
                   LIMIT ?""",
                (limit,)
            ).fetchall()
        elif email_type.startswith("followup"):
            followup_num = int(email_type.split("_")[1])
            prev_type = "cold_intro" if followup_num == 1 else f"followup_{followup_num - 1}"
            delay_days = [3, 7, 14][min(followup_num - 1, 2)]

            rows = conn.execute(
                """SELECT l.* FROM leads l
                   INNER JOIN emails_sent es ON l.id = es.lead_id
                   WHERE es.email_type = ?
                     AND l.status = 'emailed'
                     AND l.emails_sent = ?
                     AND julianday('now') - julianday(l.last_emailed) >= ?
                     AND l.email NOT IN (SELECT email FROM unsubscribed)
                     AND l.id NOT IN (
                         SELECT lead_id FROM email_tracking WHERE replied = 1
                     )
                   ORDER BY l.relevance_score DESC
                   LIMIT ?""",
                (prev_type, followup_num, delay_days, limit)
            ).fetchall()
        else:
            rows = []
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_lead_after_send(lead_id, email_type):
    """Update lead status after sending an email."""
    conn = get_connection()
    try:
        new_status = "emailed"
        conn.execute(
            """UPDATE leads
               SET status = ?, emails_sent = emails_sent + 1,
                   last_emailed = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (new_status, lead_id)
        )
        conn.commit()
    finally:
        conn.close()


def mark_lead_replied(lead_id):
    """Mark a lead as having replied."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE leads
               SET status = 'replied', last_replied = datetime('now'),
                   updated_at = datetime('now')
               WHERE id = ?""",
            (lead_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_lead_by_email(email):
    """Look up a lead by email address."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM leads WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_total_leads():
    """Count total leads in database."""
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    finally:
        conn.close()


def get_leads_by_status(status):
    """Count leads by status."""
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = ?", (status,)
        ).fetchone()[0]
    finally:
        conn.close()


# ── Email Sent Operations ───────────────────────────────────

def log_email_sent(lead_id, campaign_id, email_type, subject, body,
                   from_email, to_email, message_id=""):
    """Record a sent email."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO emails_sent
               (lead_id, campaign_id, email_type, subject, body,
                from_email, to_email, message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, campaign_id, email_type, subject, body,
             from_email, to_email, message_id)
        )
        email_id = cursor.lastrowid
        # Create tracking entry
        conn.execute(
            "INSERT INTO email_tracking (email_id) VALUES (?)", (email_id,)
        )
        conn.commit()
        return email_id
    finally:
        conn.close()


def mark_email_bounced(email_id, reason=""):
    """Mark an email as bounced."""
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE email_tracking
               SET bounced = 1, bounce_reason = ?
               WHERE email_id = ?""",
            (reason, email_id)
        )
        # Update lead status
        conn.execute(
            """UPDATE leads SET status = 'bounced', updated_at = datetime('now')
               WHERE id = (SELECT lead_id FROM emails_sent WHERE id = ?)""",
            (email_id,)
        )
        conn.commit()
    finally:
        conn.close()


def get_emails_sent_today():
    """Count emails sent today."""
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT COUNT(*) FROM emails_sent
               WHERE date(sent_at) = date('now')"""
        ).fetchone()[0]
    finally:
        conn.close()


def get_emails_sent_count(days=30):
    """Count emails sent in the last N days."""
    conn = get_connection()
    try:
        return conn.execute(
            """SELECT COUNT(*) FROM emails_sent
               WHERE sent_at >= datetime('now', ?)""",
            (f"-{days} days",)
        ).fetchone()[0]
    finally:
        conn.close()


def get_recent_sent_emails(limit=10):
    """Get the most recent sent emails with lead info and message bodies."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT es.*, l.company_name, l.country
               FROM emails_sent es
               LEFT JOIN leads l ON es.lead_id = l.id
               ORDER BY es.sent_at DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Unsubscribe Operations ──────────────────────────────────

def add_unsubscribe(email, reason=""):
    """Add an email to the unsubscribe list."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO unsubscribed (email, reason) VALUES (?, ?)",
            (email.lower().strip(), reason)
        )
        conn.execute(
            """UPDATE leads SET status = 'unsubscribed', updated_at = datetime('now')
               WHERE email = ?""",
            (email.lower().strip(),)
        )
        conn.commit()
    finally:
        conn.close()


def is_unsubscribed(email):
    """Check if an email is on the unsubscribe list."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM unsubscribed WHERE email = ?",
            (email.lower().strip(),)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# ── Warm-Up Log Operations ──────────────────────────────────

def log_warmup_day(emails_sent, bounces=0, complaints=0, daily_limit=5,
                   notes=""):
    """Log daily warm-up metrics."""
    conn = get_connection()
    today = date.today().isoformat()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO warmup_log
               (log_date, emails_sent, bounces, complaints, daily_limit, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (today, emails_sent, bounces, complaints, daily_limit, notes)
        )
        conn.commit()
    finally:
        conn.close()


def get_warmup_stats(days=7):
    """Get warm-up statistics for the last N days."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM warmup_log
               WHERE log_date >= date('now', ?)
               ORDER BY log_date DESC""",
            (f"-{days} days",)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_bounce_rate(days=7):
    """Calculate bounce rate over the last N days."""
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT
                 COALESCE(SUM(emails_sent), 0) as total,
                 COALESCE(SUM(bounces), 0) as bounces
               FROM warmup_log
               WHERE log_date >= date('now', ?)""",
            (f"-{days} days",)
        ).fetchone()
        total = row[0]
        bounces = row[1]
        return bounces / total if total > 0 else 0.0
    finally:
        conn.close()


# ── Daily Log ────────────────────────────────────────────────

def add_daily_log(action, details=""):
    """Add a daily activity log entry."""
    conn = get_connection()
    today = date.today().isoformat()
    try:
        conn.execute(
            "INSERT INTO daily_log (log_date, action, details) VALUES (?, ?, ?)",
            (today, action, details)
        )
        conn.commit()
    finally:
        conn.close()


def get_recent_activity(limit=20):
    """Get recent activity log entries."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM daily_log
               ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Dashboard Stats ──────────────────────────────────────────

def get_dashboard_stats():
    """Get all stats for the dashboard in one call."""
    conn = get_connection()
    try:
        stats = {}
        stats["total_leads"] = conn.execute(
            "SELECT COUNT(*) FROM leads"
        ).fetchone()[0]
        stats["new_leads"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'new'"
        ).fetchone()[0]
        stats["emailed"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'emailed'"
        ).fetchone()[0]
        stats["replied"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'replied'"
        ).fetchone()[0]
        stats["bounced"] = conn.execute(
            "SELECT COUNT(*) FROM leads WHERE status = 'bounced'"
        ).fetchone()[0]
        stats["unsubscribed"] = conn.execute(
            "SELECT COUNT(*) FROM unsubscribed"
        ).fetchone()[0]
        stats["sent_today"] = conn.execute(
            """SELECT COUNT(*) FROM emails_sent
               WHERE date(sent_at) = date('now')"""
        ).fetchone()[0]
        stats["sent_week"] = conn.execute(
            """SELECT COUNT(*) FROM emails_sent
               WHERE sent_at >= datetime('now', '-7 days')"""
        ).fetchone()[0]
        stats["sent_month"] = conn.execute(
            """SELECT COUNT(*) FROM emails_sent
               WHERE sent_at >= datetime('now', '-30 days')"""
        ).fetchone()[0]
        stats["sent_total"] = conn.execute(
            "SELECT COUNT(*) FROM emails_sent"
        ).fetchone()[0]

        # Country breakdown
        country_rows = conn.execute(
            """SELECT country, COUNT(*) as cnt FROM leads
               WHERE country != ''
               GROUP BY country ORDER BY cnt DESC LIMIT 10"""
        ).fetchall()
        stats["by_country"] = {r["country"]: r["cnt"] for r in country_rows}

        # Bounce rate (7 days)
        stats["bounce_rate"] = get_bounce_rate(7)

        return stats
    finally:
        conn.close()


# Auto-initialize on import
init_database()
