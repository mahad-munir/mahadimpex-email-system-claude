"""
Mahad Impex Email Marketing System — Smart Email Sender
SMTP sending engine with TLS, proper headers, and bounce handling.
"""

import smtplib
import ssl
import time
import random
import logging
import imaplib
import email as email_lib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, formatdate
from datetime import datetime

import database as db
from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    IMAP_HOST, IMAP_PORT,
    SENDER_NAME, SENDER_EMAIL, COMPANY_NAME, COMPANY_WEBSITE,
    MIN_DELAY_SECONDS, MAX_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


class EmailSender:
    """Handles SMTP connections and email sending with proper headers."""

    def __init__(self):
        self._connection = None
        self._send_count = 0

    def _connect(self):
        """Establish SMTP SSL connection."""
        try:
            context = ssl.create_default_context()
            self._connection = smtplib.SMTP_SSL(
                SMTP_HOST, SMTP_PORT, context=context, timeout=30
            )
            self._connection.login(SMTP_USER, SMTP_PASSWORD)
            logger.info(f"Connected to SMTP server {SMTP_HOST}:{SMTP_PORT}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            logger.error("Check your SMTP_PASSWORD in .env file")
            return False
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            return False

    def _ensure_connected(self):
        """Reconnect if needed."""
        try:
            if self._connection:
                status = self._connection.noop()
                if status[0] == 250:
                    return True
        except Exception:
            pass

        return self._connect()

    def _save_to_sent_folder(self, msg):
        """Save a copy of the outgoing email to IMAP 'Sent' folder."""
        try:
            imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=10)
            imap.login(SMTP_USER, SMTP_PASSWORD)
            for folder in ["Sent", "INBOX.Sent", "Sent Items", "Sent Messages"]:
                try:
                    status, _ = imap.append(
                        folder, "\\Seen",
                        imaplib.Time2Internaldate(time.time()),
                        msg.as_bytes()
                    )
                    if status == "OK":
                        break
                except Exception:
                    continue
            imap.logout()
        except Exception as e:
            logger.debug(f"Could not copy to Sent folder: {e}")

    def _build_message(self, to_email: str, subject: str, body: str,
                       reply_to: str = None) -> EmailMessage:
        """
        Build a properly formatted email message with deliverability headers.
        Plain text only — no HTML (higher deliverability).
        """
        msg = EmailMessage()

        # Core headers
        msg["From"] = formataddr((SENDER_NAME, SENDER_EMAIL))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="mahadimpex.com")
        msg["Reply-To"] = reply_to or SENDER_EMAIL

        # Deliverability headers
        msg["X-Mailer"] = "Mahad-Impex-Outreach/1.0"
        msg["Organization"] = COMPANY_NAME

        # List-Unsubscribe header (important for Gmail/Outlook)
        msg["List-Unsubscribe"] = f"<mailto:{SENDER_EMAIL}?subject=unsubscribe>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

        # Set plain text content
        msg.set_content(body)

        return msg

    def send_email(self, to_email: str, subject: str, body: str,
                   lead_id: int = None, campaign_id: int = None,
                   email_type: str = "cold_intro") -> dict:
        """
        Send a single email with full error handling.
        Returns dict with: success, message_id, error.
        """
        result = {
            "success": False,
            "message_id": "",
            "error": "",
            "to_email": to_email,
        }

        # Check unsubscribe list
        if db.is_unsubscribed(to_email):
            result["error"] = "Recipient is unsubscribed"
            logger.info(f"Skipped {to_email} — unsubscribed")
            return result

        # Ensure connection
        if not self._ensure_connected():
            result["error"] = "Failed to connect to SMTP server"
            return result

        try:
            # Build the message
            msg = self._build_message(to_email, subject, body)
            message_id = msg["Message-ID"]

            # Send it
            self._connection.send_message(msg)

            result["success"] = True
            result["message_id"] = message_id
            self._send_count += 1

            # Save copy to IMAP Sent folder so it appears in webmail
            self._save_to_sent_folder(msg)

            # Log to database
            if lead_id:
                email_id = db.log_email_sent(
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    email_type=email_type,
                    subject=subject,
                    body=body,
                    from_email=SENDER_EMAIL,
                    to_email=to_email,
                    message_id=message_id,
                )
                db.update_lead_after_send(lead_id, email_type)

            logger.info(f"✓ Sent to {to_email} | Subject: {subject[:40]}...")

        except smtplib.SMTPRecipientsRefused as e:
            result["error"] = f"Recipient refused: {e}"
            logger.warning(f"Recipient refused: {to_email}")
            if lead_id:
                # Mark as bounced
                email_id = db.log_email_sent(
                    lead_id=lead_id, campaign_id=campaign_id,
                    email_type=email_type, subject=subject, body=body,
                    from_email=SENDER_EMAIL, to_email=to_email,
                )
                db.mark_email_bounced(email_id, str(e))

        except smtplib.SMTPSenderRefused as e:
            result["error"] = f"Sender refused: {e}"
            logger.error(f"Sender refused: {e}")

        except smtplib.SMTPDataError as e:
            result["error"] = f"Data error: {e}"
            logger.error(f"SMTP data error: {e}")
            # Reconnect on data errors
            self._connection = None

        except smtplib.SMTPServerDisconnected:
            result["error"] = "Server disconnected"
            logger.warning("Server disconnected — will reconnect")
            self._connection = None
            # Retry once
            if self._ensure_connected():
                try:
                    msg = self._build_message(to_email, subject, body)
                    self._connection.send_message(msg)
                    result["success"] = True
                    result["message_id"] = msg["Message-ID"]
                    if lead_id:
                        db.log_email_sent(
                            lead_id=lead_id, campaign_id=campaign_id,
                            email_type=email_type, subject=subject, body=body,
                            from_email=SENDER_EMAIL, to_email=to_email,
                            message_id=msg["Message-ID"],
                        )
                        db.update_lead_after_send(lead_id, email_type)
                    logger.info(f"✓ Retry succeeded for {to_email}")
                except Exception as e2:
                    result["error"] = f"Retry failed: {e2}"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Unexpected error sending to {to_email}: {e}")

        return result

    def send_batch(self, emails: list, campaign_id: int = None) -> dict:
        """
        Send a batch of emails with human-like delays.
        Each item: dict with to_email, subject, body, lead_id, email_type.
        Returns summary stats.
        """
        stats = {"sent": 0, "failed": 0, "skipped": 0, "total": len(emails)}

        for i, item in enumerate(emails):
            to_email = item["to_email"]
            subject = item["subject"]
            body = item["body"]
            lead_id = item.get("lead_id")
            email_type = item.get("email_type", "cold_intro")

            result = self.send_email(
                to_email=to_email,
                subject=subject,
                body=body,
                lead_id=lead_id,
                campaign_id=campaign_id,
                email_type=email_type,
            )

            if result["success"]:
                stats["sent"] += 1
            elif "unsubscribed" in result.get("error", ""):
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

            # Human-like delay between sends
            if i < len(emails) - 1:
                delay = random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)
                logger.info(f"  Waiting {delay:.0f}s before next send...")
                time.sleep(delay)

        logger.info(
            f"\nBatch complete: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped"
        )
        return stats

    def send_test(self, to_email: str = None) -> dict:
        """Send a test email to verify SMTP configuration works."""
        if to_email is None:
            to_email = SENDER_EMAIL  # Send to self

        subject = "Mahad Impex Email System — Test"
        body = (
            f"This is a test email from the Mahad Impex Email Marketing System.\n\n"
            f"If you're reading this, your SMTP configuration is working correctly.\n\n"
            f"Timestamp: {datetime.now().isoformat()}\n"
            f"Server: {SMTP_HOST}:{SMTP_PORT}\n"
            f"From: {SENDER_EMAIL}\n\n"
            f"---\n"
            f"Aliyan Munir\n"
            f"Mahad Impex Team\n"
            f"Website: mahadimpex.com\n"
            f"Call/WhatsApp: +92 300 9657831\n\n"
            f"Faisalabad, Punjab, Pakistan\n"
            f"To stop receiving these emails, reply with \"unsubscribe\"."
        )

        return self.send_email(to_email, subject, body)

    def close(self):
        """Close the SMTP connection."""
        try:
            if self._connection:
                self._connection.quit()
                logger.info("SMTP connection closed")
        except Exception:
            pass
        self._connection = None


def check_for_replies_and_bounces():
    """
    Check IMAP inbox for replies, bounces, and unsubscribe requests.
    Updates database accordingly.
    """
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(SMTP_USER, SMTP_PASSWORD)
        mail.select("INBOX")

        # Search for unread messages
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            return {"replies": 0, "bounces": 0, "unsubscribes": 0}

        msg_nums = messages[0].split()
        replies = 0
        bounces = 0
        unsubscribes = 0

        for num in msg_nums[-50:]:  # Process last 50 unread
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue

            msg = email_lib.message_from_bytes(msg_data[0][1])
            from_addr = email_lib.utils.parseaddr(msg["From"])[1].lower()
            subject = str(msg.get("Subject", "")).lower()

            # Get body text
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        except Exception:
                            pass
                        break
            else:
                try:
                    body_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                except Exception:
                    pass

            body_lower = body_text.lower()

            # Check for unsubscribe
            if "unsubscribe" in subject or "unsubscribe" in body_lower:
                db.add_unsubscribe(from_addr, "Requested via email reply")
                unsubscribes += 1
                logger.info(f"Unsubscribe processed: {from_addr}")
                continue

            # Check for bounce
            if any(indicator in subject for indicator in
                   ["undeliverable", "delivery failed", "returned mail",
                    "mail delivery failed", "failure notice",
                    "delivery status notification"]):
                # Try to find the original recipient
                lead = db.get_lead_by_email(from_addr)
                if lead:
                    db.mark_email_bounced(lead["id"], "Bounce notification")
                bounces += 1
                logger.info(f"Bounce detected: {from_addr}")
                continue

            # Check for auto-reply / out-of-office (don't count as real replies)
            if any(indicator in subject for indicator in
                   ["out of office", "auto-reply", "automatic reply",
                    "autoreply", "on vacation", "away from office"]):
                continue

            # It's a genuine reply
            lead = db.get_lead_by_email(from_addr)
            if lead:
                db.mark_lead_replied(lead["id"])
                replies += 1
                logger.info(f"Reply received from: {from_addr}")

        mail.logout()

        result = {
            "replies": replies,
            "bounces": bounces,
            "unsubscribes": unsubscribes,
        }
        logger.info(f"Inbox check: {result}")
        return result

    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP error: {e}")
        return {"replies": 0, "bounces": 0, "unsubscribes": 0}
    except Exception as e:
        logger.error(f"Error checking inbox: {e}")
        return {"replies": 0, "bounces": 0, "unsubscribes": 0}
