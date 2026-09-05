"""
Mahad Impex Email Marketing System — Lead Finder Engine
Discovers potential textile buyers from public web sources.
"""

import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

import database as db
from email_verifier import verify_email
from config import (
    TARGET_MARKETS, PRODUCT_LINES, SEARCH_QUERIES, LOG_DIR
)

logger = logging.getLogger(__name__)

# ── Browser-like request headers ─────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# Blacklisted prefix keywords (departments that should NEVER be emailed)
BLACKLIST_PREFIX_KEYWORDS = {
    # Careers & HR
    "career", "careers", "job", "jobs", "hiring", "recruitment", "recruiting", "talent", "hr",
    # Customer service & consumer support
    "help", "support", "customercare", "customerservice", "feedback", "survey", "care", "service",
    # PR, IR, Media, Stock
    "shareholder", "investor", "investors", "press", "media", "pr", "ir", "news",
    # Legal, Compliance, Privacy
    "privacy", "legal", "compliance", "security", "gdpr", "dmca", "copyright", "terms", "law",
    # Financial & Billing
    "billing", "invoice", "invoices", "accounting", "account", "accounts", "finance", "payment", "payments",
    # System & automated
    "noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster", "webmaster", "abuse", "bounce",
    "root", "admin", "tech", "web", "sysadmin", "dev",
    # Marketing & Subscription
    "newsletter", "unsubscribe", "subscribe", "promo", "affiliate", "marketing", "ads",
}

# Domains to completely ignore (registrars, tech giants, social platforms, invalid services)
BLACKLIST_DOMAINS = {
    "computershare.com", "google.com", "microsoft.com", "apple.com", "w3.org", "schema.org",
    "sentry.io", "cloudflare.com", "github.com", "gitlab.com", "example.com", "domain.com",
    "wordpress.com", "shopify.com", "facebook.com", "twitter.com", "instagram.com", "linkedin.com",
    "pinterest.com", "youtube.com", "tiktok.com", "trustpilot.com", "yelp.com", "wikipedia.org",
}

# Common B2B-friendly email prefixes (higher relevance)
B2B_PREFIXES = {
    "info", "sales", "purchase", "purchasing", "procurement",
    "import", "imports", "sourcing", "buying", "buyer",
    "contact", "enquiry", "enquiries", "inquiry",
    "trade", "export", "commercial", "office", "hello",
}

# Email extraction regex
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)


def is_blacklisted_email(email: str) -> bool:
    """Check if an email belongs to an irrelevant department or blacklisted domain."""
    email = email.lower().strip()
    if "@" not in email:
        return True
    prefix, domain = email.split("@", 1)

    # Check blacklisted domains or self domain
    if domain in BLACKLIST_DOMAINS or "mahadimpex.com" in domain:
        return True

    # Check exact short department abbreviations
    if prefix in ("ir", "pr", "hr", "it", "ap", "ar", "ad", "ads", "faq", "jobs", "care"):
        return True

    # Check if any blacklisted keyword is inside the username prefix
    for kw in BLACKLIST_PREFIX_KEYWORDS:
        if kw in prefix:
            return True

    return False


def _score_email_priority(email: str) -> int:
    """Score an email for B2B buyer relevance to select the single best contact per company."""
    prefix = email.split("@")[0].lower()

    # Priority 1: Direct sourcing / purchasing / procurement (Best)
    tier1 = {"sourcing", "purchasing", "purchase", "procurement", "buyer", "buying", "import", "imports", "supplychain"}
    for kw in tier1:
        if kw in prefix:
            return 100

    # Priority 2: Commercial / trade / sales
    tier2 = {"trade", "commercial", "export", "sales"}
    for kw in tier2:
        if kw in prefix:
            return 75

    # Priority 3: Named individual (e.g. john.smith@company.com)
    if ("." in prefix or "_" in prefix) and len(prefix) > 5 and prefix not in B2B_PREFIXES:
        return 60

    # Priority 4: General business contact
    tier4 = {"info", "contact", "enquiry", "enquiries", "inquiry", "office", "hello"}
    for kw in tier4:
        if kw in prefix:
            return 40

    return 20


def _get_session():
    """Create a requests session with browser-like headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    return session


def _polite_delay():
    """Random delay to avoid aggressive scraping patterns."""
    time.sleep(random.uniform(2.0, 5.0))


def _extract_emails_from_text(text: str) -> set:
    """Extract email addresses from a block of text."""
    raw = set(EMAIL_REGEX.findall(text.lower()))
    cleaned = set()
    for email in raw:
        # Skip image file extensions mistakenly captured
        if any(email.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")):
            continue
        # Skip blacklisted / irrelevant department emails
        if is_blacklisted_email(email):
            continue
        cleaned.add(email)
    return cleaned


def _calculate_relevance(email: str, page_text: str, country: str) -> int:
    """Score lead relevance 0-100 based on context clues."""
    score = 40  # Base score

    prefix = email.split("@")[0].lower()

    # B2B-friendly prefix bonus
    if prefix in B2B_PREFIXES:
        score += 15
    # Named contact (e.g., john.smith@) is better than generic
    elif "." in prefix and len(prefix) > 5:
        score += 20

    page_lower = page_text.lower()

    # Textile industry keywords
    textile_keywords = [
        "textile", "fabric", "linen", "towel", "bedding", "cotton",
        "garment", "apparel", "home textile", "bed sheet", "duvet",
        "importer", "distributor", "wholesaler", "retail", "hospitality",
        "sourcing", "procurement", "supply chain", "manufacturer",
    ]
    keyword_hits = sum(1 for kw in textile_keywords if kw in page_lower)
    score += min(keyword_hits * 5, 25)

    # Country match bonus
    if country.lower() in page_lower:
        score += 5

    return min(score, 100)


def _guess_first_name(email: str, contact_person: str) -> str:
    """Try to extract a first name from email or contact person."""
    if contact_person:
        return contact_person.split()[0].title()
    prefix = email.split("@")[0]
    # Patterns like john.smith, john_smith, jsmith
    for sep in [".", "_", "-"]:
        if sep in prefix:
            parts = prefix.split(sep)
            if len(parts[0]) > 1:
                return parts[0].title()
    # If prefix is a name-like word
    if prefix.isalpha() and len(prefix) > 2 and prefix not in B2B_PREFIXES:
        return prefix.title()
    return ""


def _extract_company_from_domain(domain: str) -> str:
    """Guess company name from domain."""
    name = domain.split(".")[0]
    # Remove common suffixes
    for suffix in ["inc", "llc", "ltd", "co", "corp", "group", "intl"]:
        name = name.replace(suffix, "")
    return name.replace("-", " ").replace("_", " ").strip().title()


def search_duckduckgo(query: str, max_results: int = 15) -> list:
    """
    Search DuckDuckGo and return result URLs.
    Uses the HTML interface to avoid API restrictions.
    """
    results = []
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
    return results


def scrape_page_for_emails(url: str, session=None) -> dict:
    """
    Visit a web page and extract emails and company context.
    Returns dict with emails, company_name, page_text.
    """
    if session is None:
        session = _get_session()

    result = {"emails": set(), "company_name": "", "page_text": ""}

    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove script/style noise
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        page_text = soup.get_text(separator=" ", strip=True)
        result["page_text"] = page_text[:5000]  # Limit for efficiency

        # Extract emails from page text
        result["emails"] = _extract_emails_from_text(page_text)

        # Also check href="mailto:..." links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                if email and "@" in email:
                    result["emails"].add(email)

        # Try to get company name from title or og:site_name
        og_site = soup.find("meta", property="og:site_name")
        if og_site and og_site.get("content"):
            result["company_name"] = og_site["content"].strip()
        elif soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Take first segment before common separators
            for sep in [" | ", " - ", " – ", " — ", " :: "]:
                if sep in title:
                    title = title.split(sep)[0].strip()
                    break
            result["company_name"] = title[:80]

    except requests.exceptions.Timeout:
        logger.debug(f"Timeout scraping {url}")
    except requests.exceptions.RequestException as e:
        logger.debug(f"Request error scraping {url}: {e}")
    except Exception as e:
        logger.debug(f"Error scraping {url}: {e}")

    return result


def find_contact_page(base_url: str, session=None) -> str:
    """Try to find and return the contact page URL."""
    if session is None:
        session = _get_session()

    contact_paths = [
        "/contact", "/contact-us", "/contact.html", "/contactus",
        "/about/contact", "/get-in-touch", "/reach-us",
        "/about", "/about-us", "/about.html",
    ]

    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in contact_paths:
        url = base + path
        try:
            resp = session.head(url, timeout=8, allow_redirects=True)
            if resp.status_code == 200:
                return url
        except Exception:
            continue

    return ""


def discover_leads_for_market(country_name: str, country_code: str,
                               product_name: str, product_keywords: list,
                               max_leads: int = 20) -> int:
    """
    Run search queries for a specific market + product combination.
    Returns number of new leads added.
    """
    session = _get_session()
    new_leads = 0

    # Build search queries
    queries = []
    for template in SEARCH_QUERIES[:6]:  # Limit queries to avoid rate limits
        query = template.format(
            product=product_name,
            country=country_name,
        )
        queries.append(query)

    for query in queries:
        if new_leads >= max_leads:
            break

        logger.info(f"Searching: {query}")
        results = search_duckduckgo(query, max_results=10)
        _polite_delay()

        for result in results:
            if new_leads >= max_leads:
                break

            url = result.get("url", "")
            snippet = result.get("snippet", "")
            title = result.get("title", "")

            if not url:
                continue

            # Skip social media, marketplaces we don't want
            skip_domains = [
                "facebook.com", "twitter.com", "instagram.com",
                "youtube.com", "linkedin.com", "pinterest.com",
                "amazon.com", "ebay.com", "alibaba.com",
                "wikipedia.org", "reddit.com",
            ]
            domain = urlparse(url).netloc.lower()
            if any(sd in domain for sd in skip_domains):
                continue

            # Check snippet for emails first (fast)
            snippet_emails = _extract_emails_from_text(snippet + " " + title)

            # Scrape the page
            page_data = scrape_page_for_emails(url, session)
            all_emails = snippet_emails | page_data["emails"]

            # Also try contact page
            if not all_emails:
                contact_url = find_contact_page(url, session)
                if contact_url:
                    _polite_delay()
                    contact_data = scrape_page_for_emails(contact_url, session)
                    all_emails = contact_data["emails"]
                    if not page_data["company_name"] and contact_data["company_name"]:
                        page_data["company_name"] = contact_data["company_name"]

            if not all_emails:
                continue

            company = page_data["company_name"] or _extract_company_from_domain(domain)
            page_text = page_data["page_text"]

            # Group discovered emails by their company domain
            domain_groups = {}
            for email in all_emails:
                if is_blacklisted_email(email):
                    continue
                if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email):
                    continue
                dom = email.split("@")[1].lower()
                domain_groups.setdefault(dom, []).append(email)

            for dom, emails_in_dom in domain_groups.items():
                if new_leads >= max_leads:
                    break

                # Check if this company domain already has a contact in our database
                if db.domain_exists(dom):
                    logger.debug(f"Skipping domain {dom} — company already exists in database")
                    continue

                # Sort by B2B relevance priority and pick ONLY the single best email
                emails_in_dom.sort(key=_score_email_priority, reverse=True)
                best_email = emails_in_dom[0]

                # Verify email (MX check only — fast)
                verification = verify_email(best_email, deep_check=False)
                if not verification["valid"]:
                    logger.debug(f"Skipped invalid email: {best_email} — {verification['reason']}")
                    continue

                # Calculate relevance
                relevance = _calculate_relevance(best_email, page_text, country_name)

                # Try to get a first name
                first_name = _guess_first_name(best_email, "")

                # Store lead (guaranteed 1 contact per company domain)
                lead_id = db.add_lead(
                    email=best_email,
                    company_name=company,
                    contact_person="",
                    first_name=first_name,
                    country=country_name,
                    country_code=country_code,
                    industry="textiles",
                    product_interest=product_name,
                    source="web_search",
                    source_url=url,
                    relevance_score=relevance,
                )

                if lead_id:
                    new_leads += 1
                    logger.info(f"  ✓ New buyer lead: {best_email} ({company}, {country_name}) score={relevance}")

            _polite_delay()

    return new_leads


def run_lead_discovery(max_leads_per_combo: int = 10,
                       markets: list = None,
                       products: list = None) -> int:
    """
    Main entry point: discover leads across all target markets and products.
    Returns total new leads found.
    """
    if markets is None:
        markets = TARGET_MARKETS
    if products is None:
        products = PRODUCT_LINES

    total_new = 0

    for market in markets:
        for product in products:
            logger.info(
                f"\n{'='*60}\n"
                f"  Searching: {product['name']} → {market['country']}\n"
                f"{'='*60}"
            )
            try:
                new = discover_leads_for_market(
                    country_name=market["country"],
                    country_code=market["code"],
                    product_name=product["name"],
                    product_keywords=product["keywords"],
                    max_leads=max_leads_per_combo,
                )
                total_new += new
                logger.info(f"  Found {new} new leads for {product['name']} in {market['country']}")
            except Exception as e:
                logger.error(f"  Error searching {product['name']} in {market['country']}: {e}")

            # Longer delay between market/product combos
            time.sleep(random.uniform(5, 10))

    db.add_daily_log("lead_discovery", f"Found {total_new} new leads")
    logger.info(f"\nTotal new leads found: {total_new}")
    return total_new


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    # Quick test: search 1 market, 1 product
    run_lead_discovery(
        max_leads_per_combo=5,
        markets=TARGET_MARKETS[:1],
        products=PRODUCT_LINES[:1],
    )
