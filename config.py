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
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# ── Sender Identity & Accounts ──────────────────────────────
COMPANY_NAME = "Mahad Impex"
COMPANY_WEBSITE = "https://mahadimpex.com"
COMPANY_PHONE = "+92 300 9657831"
COMPANY_ADDRESS = "Faisalabad, Punjab, Pakistan"
COMPANY_TAGLINE = "Textile Sourcing & Buying House"

# Account 1: Muhammad Munir (Warmed up with ~260 prior sends — dynamically scaled 35->45/day)
ACCOUNT_MUNIR = {
    "id": "munir",
    "name": "Muhammad Munir",
    "title": "Marketing Director",
    "email": os.getenv("SMTP_USER_MUNIR", "munir@mahadimpex.com"),
    "password": os.getenv("SMTP_PASSWORD_MUNIR", os.getenv("SMTP_PASSWORD", "")),
    "smtp_host": SMTP_HOST,
    "smtp_port": SMTP_PORT,
    "imap_host": IMAP_HOST,
    "imap_port": IMAP_PORT,
    "is_warmed_up": True,
    "daily_limit": int(os.getenv("MUNIR_DAILY_LIMIT")) if os.getenv("MUNIR_DAILY_LIMIT") else None,
    "signature": """Muhammad Munir
Mahad Impex Team 
Website: mahadimpex.com
Call/WhatsApp: +92 300 9657831""",
}

# Account 2: Aliyan Munir (In warm-up schedule — currently 5 emails/day)
ACCOUNT_ALIYAN = {
    "id": "aliyan",
    "name": "Aliyan Munir",
    "title": "Head of International Sourcing",
    "email": os.getenv("SMTP_USER", "aliyanmunir@mahadimpex.com"),
    "password": os.getenv("SMTP_PASSWORD", ""),
    "smtp_host": SMTP_HOST,
    "smtp_port": SMTP_PORT,
    "imap_host": IMAP_HOST,
    "imap_port": IMAP_PORT,
    "is_warmed_up": False,
    "daily_limit": None,  # Calculated dynamically from warmup schedule
    "signature": """Aliyan Munir
Mahad Impex Team 
Website: mahadimpex.com
Call/WhatsApp: +92 300 9657831""",
}

# Active accounts in campaign sending order
ACCOUNTS = [ACCOUNT_MUNIR, ACCOUNT_ALIYAN]

# Default identity (for backward compatibility)
SENDER_NAME = ACCOUNT_ALIYAN["name"]
SENDER_TITLE = ACCOUNT_ALIYAN["title"]
SENDER_EMAIL = ACCOUNT_ALIYAN["email"]

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
        "short_keyword": "bed linen",
        "keywords": ["bed linen", "bed sheets", "duvet covers", "bedding",
                     "bed sets", "pillowcases", "fitted sheets"],
        "description": "100% combed cotton 144TC to 800TC percales and lustrous sateens — duvet sets, fitted sheets, flat sheets, and pillowcases for wholesale and institutional supply.",
        "usp": "Direct mill-gate FOB pricing with OEKO-TEX Standard 100 & GOTS certifications. 4-stage in-line weaving and AQL 2.5 final inspection.",
    },
    {
        "name": "Terry Towels & Bath Linen",
        "short_keyword": "towel",
        "keywords": ["towels", "bath towels", "terry towels", "bath linen",
                     "hand towels", "bath robes", "hotel towels"],
        "description": "400 to 700 GSM ring-spun and zero-twist 100% cotton bath towels, bath sheets, hand towels, and bathrobes with vat-dyed commercial colorfastness.",
        "usp": "Faisalabad is the world's #1 terry towel export hub. Double-stitched institutional hems with high-absorbency zero-twist yarn.",
    },
    {
        "name": "Knitted Garments",
        "short_keyword": "apparel",
        "keywords": ["t-shirts", "polo shirts", "hoodies", "activewear",
                     "sweatshirts", "knitted garments", "casual wear"],
        "description": "Custom knitted apparel — 160 to 320 GSM single jersey, pique, and French terry T-shirts, polos, and fleece hoodies with custom Pantone dyeing.",
        "usp": "Competitive FOB pricing with 20-30 day lead times and agile MOQs from 500 pieces per style.",
    },
    {
        "name": "Kitchen & Table Linen",
        "short_keyword": "table linen",
        "keywords": ["kitchen towels", "aprons", "table cloths", "napkins",
                     "oven mitts", "kitchen linen", "table linen"],
        "description": "Yarn-dyed jacquard kitchen towels, heavy waffle weaves, restaurant-grade tablecloths, and napkins built for heavy commercial laundering.",
        "usp": "High-durability commercial constructions with custom yarn-dyed checks, stripes, and embroidery options.",
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
ENABLE_FOLLOWUPS = os.getenv("ENABLE_FOLLOWUPS", "false").lower() in ("true", "1", "yes")
MAX_FOLLOWUPS = int(os.getenv("MAX_FOLLOWUPS", "3")) if ENABLE_FOLLOWUPS else 0
FOLLOWUP_DELAYS_DAYS = [3, 7, 14]  # Days between follow-ups
RE_ENGAGE_AFTER_DAYS = 60   # Re-engagement email after N days

# ── Email Content Rules ──────────────────────────────────────
MAX_SUBJECT_LENGTH = 60
MAX_EMAIL_LINKS = 1         # Only website link
MAX_EXCLAMATION_MARKS = 1
INCLUDE_UNSUBSCRIBE = False
INCLUDE_PHYSICAL_ADDRESS = False
