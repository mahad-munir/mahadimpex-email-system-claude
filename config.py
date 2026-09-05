"""
Mahad Impex Email Marketing System — Central Configuration
All settings are loaded from .env and defined here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"
DB_PATH = DATA_DIR / "mahadimpex.db"

# Create dirs on import
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Load environment
load_dotenv(BASE_DIR / ".env")

# ── SMTP (cPanel SSL) ───────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "mail.mahadimpex.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "aliyanmunir@mahadimpex.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── IMAP (for bounce/reply reading) ─────────────────────────
IMAP_HOST = os.getenv("IMAP_HOST", "mail.mahadimpex.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))

# ── Gemini AI ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# ── Sender Identity ─────────────────────────────────────────
SENDER_NAME = "Aliyan Munir"
SENDER_TITLE = "Sourcing Specialist"
SENDER_EMAIL = SMTP_USER
COMPANY_NAME = "Mahad Impex"
COMPANY_WEBSITE = "https://mahadimpex.com"
COMPANY_PHONE = "+92 300 9657831"
COMPANY_ADDRESS = "Faisalabad, Punjab, Pakistan"
COMPANY_TAGLINE = "Textile Sourcing & Buying House"

# ── Target Markets (ordered by priority) ─────────────────────
# Pakistan's hottest textile export destinations (2025-2026)
TARGET_MARKETS = [
    {"country": "United States", "code": "US", "timezone": "America/New_York"},
    {"country": "United Kingdom", "code": "UK", "timezone": "Europe/London"},
    {"country": "Germany", "code": "DE", "timezone": "Europe/Berlin"},
    {"country": "Netherlands", "code": "NL", "timezone": "Europe/Amsterdam"},
    {"country": "Australia", "code": "AU", "timezone": "Australia/Sydney"},
    {"country": "Canada", "code": "CA", "timezone": "America/Toronto"},
    {"country": "Belgium", "code": "BE", "timezone": "Europe/Brussels"},
    {"country": "Spain", "code": "ES", "timezone": "Europe/Madrid"},
    {"country": "France", "code": "FR", "timezone": "Europe/Paris"},
    {"country": "Italy", "code": "IT", "timezone": "Europe/Rome"},
    {"country": "United Arab Emirates", "code": "AE", "timezone": "Asia/Dubai"},
    {"country": "Poland", "code": "PL", "timezone": "Europe/Warsaw"},
]

# ── Product Lines ────────────────────────────────────────────
PRODUCT_LINES = [
    {
        "name": "Bed Linen & Bed Sets",
        "keywords": ["bed linen", "bed sheets", "duvet covers", "bedding",
                     "bed sets", "pillowcases", "fitted sheets"],
        "description": "Premium combed-cotton bed sets, duvets, fitted sheets, "
                       "and pillowcases — woven for comfort and durability at scale.",
        "usp": "Pakistan is the world's 3rd largest bed linen exporter. "
               "Our manufacturing partners hold OEKO-TEX and GOTS certifications.",
    },
    {
        "name": "Terry Towels & Bath Linen",
        "keywords": ["towels", "bath towels", "terry towels", "bath linen",
                     "hand towels", "bath robes", "hotel towels"],
        "description": "Absorbent terry towels, robes, and bath linen — "
                       "widely supplied to hospitality chains and retailers.",
        "usp": "Pakistan is the world's largest terry towel exporter. "
               "We offer 400-700 GSM options in ring-spun and zero-twist.",
    },
    {
        "name": "Knitted Garments",
        "keywords": ["t-shirts", "polo shirts", "hoodies", "activewear",
                     "sweatshirts", "knitted garments", "casual wear"],
        "description": "Custom knitted apparel — T-shirts, polos, hoodies, "
                       "and activewear with full branding and packaging options.",
        "usp": "Competitive pricing with 20-30 day lead times. "
               "MOQ as low as 500 pieces per style.",
    },
    {
        "name": "Kitchen & Table Linen",
        "keywords": ["kitchen towels", "aprons", "table cloths", "napkins",
                     "oven mitts", "kitchen linen", "table linen"],
        "description": "Kitchen towels, aprons, tablecloths, and napkins — "
                       "durable weaves for everyday use and hospitality.",
        "usp": "Full custom printing and embroidery capabilities.",
    },
]

# ── Lead Search Queries ──────────────────────────────────────
SEARCH_QUERIES = [
    # B2B textile importers and wholesale buyers
    'textile importer distributor {country} "contact" OR "about" email',
    '{product} wholesale distributor {country} contact email',
    'home textiles buying house sourcing {country} email',
    '{product} procurement sourcing agent {country} email',
    'commercial linen hospitality supplier {country} contact email',
    'institutional textiles distributor {country} email',
    '{product} B2B wholesale import {country} email',
    'hotel linen wholesale supplier {country} contact email',
]

# ── Warm-Up Schedule ────────────────────────────────────────
# Daily sending limits per week after domain creation
WARMUP_SCHEDULE = {
    1: 5,       # Week 1: 5 emails/day
    2: 10,      # Week 2: 10
    3: 20,      # Week 3: 20
    4: 35,      # Week 4: 35
    5: 50,      # Week 5: 50
    6: 75,      # Week 6: 75
    7: 100,     # Week 7+: cruising
}
MAX_DAILY_SENDS = 100  # Hard ceiling

# ── Sending Rules ────────────────────────────────────────────
MIN_DELAY_SECONDS = int(os.getenv("MIN_DELAY_SECONDS", "90"))
MAX_DELAY_SECONDS = int(os.getenv("MAX_DELAY_SECONDS", "210"))
SEND_WINDOW_START = 9       # 9 AM (recipient local time)
SEND_WINDOW_END = 17        # 5 PM (recipient local time)
SEND_ON_WEEKENDS = False    # Skip Sat/Sun
MAX_BOUNCE_RATE = 0.03      # Pause if > 3% bounces
MAX_FOLLOWUPS = 3           # Follow-up attempts per lead
FOLLOWUP_DELAYS_DAYS = [3, 7, 14]  # Days between follow-ups
RE_ENGAGE_AFTER_DAYS = 60   # Re-engagement email after N days

# ── Email Content Rules ──────────────────────────────────────
MAX_SUBJECT_LENGTH = 60
MAX_EMAIL_LINKS = 1         # Only website link
MAX_EXCLAMATION_MARKS = 1
INCLUDE_UNSUBSCRIBE = False
INCLUDE_PHYSICAL_ADDRESS = False
