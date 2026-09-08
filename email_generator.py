"""
Mahad Impex Email Marketing System — AI Email Generator
Uses Google Gemini to generate unique, human-sounding emails.
"""

import json
import random
import logging
import time
from pathlib import Path
from google import genai

from config import (
    GEMINI_API_KEY, GEMINI_MODEL, TEMPLATES_DIR,
    SENDER_NAME, SENDER_TITLE, SENDER_EMAIL,
    COMPANY_NAME, COMPANY_WEBSITE, COMPANY_PHONE,
    COMPANY_ADDRESS, COMPANY_TAGLINE,
    PRODUCT_LINES,
)
from spam_guard import check_email, sanitize_email_content, get_unsubscribe_footer

logger = logging.getLogger(__name__)

# Load email context templates
_contexts_path = TEMPLATES_DIR / "email_contexts.json"
_contexts = {}
if _contexts_path.exists():
    with open(_contexts_path, "r", encoding="utf-8") as f:
        _contexts = json.load(f)

# Initialize Gemini client
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _pick_product_context(product_interest: str = "") -> dict:
    """Select the best product line context for the lead."""
    if product_interest:
        for p in PRODUCT_LINES:
            if any(kw in product_interest.lower() for kw in p["keywords"]):
                return p
    return random.choice(PRODUCT_LINES)


def _build_system_prompt(account: dict = None) -> str:
    """Build the system prompt instructing Gemini on voice, persona, and constraints."""
    company = _contexts.get("company_profile", {})
    account_id = "munir" if (account and "munir" in account.get("id", "").lower()) else "aliyan"

    sender_name = account.get("name", SENDER_NAME) if account else SENDER_NAME
    sender_title = account.get("title", SENDER_TITLE) if account else SENDER_TITLE
    signature = account.get("signature") if account else f"""Aliyan Munir
Mahad Impex Team 
Website: mahadimpex.com
Call/WhatsApp: +92 300 9657831"""

    if account_id == "munir":
        persona_brief = (
            f"You are writing as {sender_name}, {sender_title} at {COMPANY_NAME}.\n"
            "YOUR ROLE & STRATEGY: Commercial & Margins Specialist. You talk directly to B2B procurement "
            "directors and wholesale buyers about FOB mill-gate pricing, margin optimization, eliminating middleman "
            "trading markups (12-18% savings), and transparent FOB price benchmarking against their current landed costs."
        )
    else:
        persona_brief = (
            f"You are writing as {sender_name}, {sender_title} at {COMPANY_NAME}.\n"
            "YOUR ROLE & STRATEGY: Head of Sourcing & Product Quality on the ground in Faisalabad. "
            "You talk to buyers about technical fabric constructions (percales, sateens, GSM weights, yarn counts), "
            "on-site 4-stage AQL 2.5 mill inspections, rapid sampling (4-day lab dips), and offering free physical fabric swatch hangers."
        )

    return f"""{persona_brief}

COMPANY BACKGROUND:
- {COMPANY_NAME} is a direct textile buying house based in Faisalabad, Pakistan (the world's textile manufacturing hub).
- Website: {COMPANY_WEBSITE} | Phone/WhatsApp: +92 300 9657831
- Mill partners hold OEKO-TEX Standard 100, GOTS, and BSCI/Sedex certifications.

CRITICAL WRITING RULES:
1. Write like an experienced textile professional emailing a colleague — NOT like an AI, an agency copywriter, or a brochure.
2. Keep emails ULTRA-SHORT: 65 to 95 words maximum (excluding signature).
3. Structure: Exactly 3 brief paragraphs (1-2 sentences each). Lots of white space, fast to scan on a phone in 10 seconds.
4. NO CORPORATE CLICHÉS: NEVER say "I hope this email finds you well", "Good day", "Late deliveries and inconsistent quality...", "Every shipment goes through...", "We recently fulfilled a 40,000-piece order...", "With cotton prices stabilizing...".
5. SPAM SHIELD: NEVER use: free, guaranteed, limited time, act now, exclusive deal, urgent, risk free, incredible, best price, cheap, revolutionary.
6. Plain text only — NO bullet points, NO markdown bolding (* or **), NO HTML.
7. End with ONE single, low-friction question or CTA (offering FOB benchmark comparison or free fabric swatches).
8. Always end with the EXACT provided signature.

EMAIL SIGNATURE:
{signature}"""


def _build_cold_intro_prompt(lead: dict, product: dict, account: dict = None) -> str:
    """Build the prompt for a high-converting cold introduction email."""
    account_id = "munir" if (account and "munir" in account.get("id", "").lower()) else "aliyan"
    persona_data = _contexts.get("persona_strategies", {}).get(account_id, {})
    angles = persona_data.get("angles", [])
    selected_angle = random.choice(angles) if angles else {
        "theme": "Direct mill-gate sourcing advantage from Pakistan",
        "hook_instruction": "Mention reaching out directly from Faisalabad where we connect overseas distributors with audited mills.",
        "cta": "Would you be open to reviewing our current FOB price sheet for comparison against your current landed costs?"
    }

    first_name = lead.get("first_name")
    company_name = lead.get("company_name", "your company")
    short_company = company_name.split()[0].strip(",").strip(".") if company_name else "team"

    if first_name:
        greeting = f"Hi {first_name},"
    else:
        greeting = f"Hi {short_company} team,"

    product_name = product.get("name", "Home Textiles")
    product_kw = product.get("short_keyword", "textile")
    product_desc = product.get("description", "")
    product_usp = product.get("usp", "")

    sample_subjects = [
        f"quick question re: {product_kw} specs",
        f"faisalabad mill pricing / {short_company}",
        f"{product_kw} specs / {short_company}",
        f"samples for {short_company}",
        f"quick question, {first_name or short_company}",
    ]

    return f"""Write an ultra-short, peer-to-peer B2B cold email to a wholesale buyer / importer.

RECIPIENT INFO:
- Company: {company_name}
- Contact: {first_name or 'Not specified (address ' + short_company + ' team)'}
- Country: {lead.get('country', '')}
- Likely product focus: {lead.get('product_interest') or product_name}

YOUR PRODUCT SPECS (naturally mention 1-2 concrete specs):
- Product: {product_name}
- Construction & Specs: {product_desc}
- Manufacturing Advantage: {product_usp}

STRATEGIC ANGLE FOR THIS EMAIL:
- Angle Theme: {selected_angle['theme']}
- Hook Guidance: {selected_angle['hook_instruction']}
- Target Call-to-Action (CTA): {selected_angle['cta']}

START THE EMAIL WITH EXACTLY: {greeting}

STRICT WRITING RULES:
1. LENGTH: 65 to 95 words MAXIMUM (excluding signature). Keep it punchy and clear.
2. PARAGRAPHS: 3 short paragraphs total (1-2 sentences each).
3. TONE: Peer-to-peer, confident, knowledgeable, direct. No corporate buzzwords, no lecturing.
4. NO CLICHÉS: NEVER start with "Late deliveries...", "Every shipment goes through...", "We recently fulfilled a 40,000-piece order...", "With cotton prices stabilizing...".
5. SUBJECT LINE: Must be 2 to 5 words MAXIMUM. Natural casing or lowercase. Must look like a real human email, NOT a marketing pitch.
   Example subject styles: {', '.join(sample_subjects)}

FORMAT YOUR RESPONSE EXACTLY AS:
SUBJECT: [2 to 5 words subject line]
BODY:
[email body ending with the exact signature provided in system prompt]"""


def _build_followup_prompt(lead: dict, product: dict,
                            followup_num: int, previous_subject: str = "") -> str:
    """Build prompt for follow-up emails."""
    followup_config = _contexts.get("followup_angles", {})

    if followup_num == 1:
        config = followup_config.get("followup_1", {})
        instruction = (
            "Write a gentle first follow-up. Reference your previous email briefly. "
            "Add a NEW specific detail about your product or a relevant case study. "
            "Keep it shorter than the original — 50-100 words."
        )
    elif followup_num == 2:
        config = followup_config.get("followup_2", {})
        instruction = (
            "Write a second follow-up that provides genuine value — share a market insight, "
            "a specific capability, or ask a relevant question about their needs. "
            "Don't reference previous emails explicitly. 50-80 words."
        )
    else:
        config = followup_config.get("followup_3", {})
        instruction = (
            "Write a final, brief follow-up. Be respectful — acknowledge they may be busy "
            "or it may not be the right time. Leave the door open for future contact. "
            "No pressure at all. 40-60 words. This is the last email in the sequence."
        )

    greeting_styles = _contexts.get("greeting_styles", ["Hi {first_name},"])
    if lead.get("first_name"):
        greeting = random.choice(greeting_styles).format(first_name=lead["first_name"])
    else:
        greeting = random.choice(["Hi there,", "Hello,", "Good day,"])

    contact_name_display = lead.get('first_name') or 'Not specified (address the company or team)'

    return f"""Write follow-up #{followup_num} to a textile buyer who hasn't replied.

RECIPIENT INFO:
- Company: {lead.get('company_name', 'their company')}
- Contact name: {contact_name_display}
- Country: {lead.get('country', '')}
- Product interest: {lead.get('product_interest', product['name'])}
- Previous subject line: {previous_subject}

PRODUCT CONTEXT:
- {product['name']}: {product['description']}
- USP: {product['usp']}

TONE: {config.get('tone', 'Friendly, brief')}
THEME: {config.get('theme', 'Follow-up reminder')}

{instruction}

START WITH: {greeting}

FORMAT YOUR RESPONSE EXACTLY AS:
SUBJECT: [subject line — can reference the thread naturally]
BODY:
[your email body ending with the exact signature]"""


def _parse_ai_response(response_text: str) -> tuple:
    """Parse Gemini response into subject and body with high-conversion cleaning."""
    subject = ""
    body = ""

    lines = response_text.strip().split("\n")

    body_started = False
    body_lines = []

    for line in lines:
        clean_line = line.strip()
        if clean_line.upper().startswith("SUBJECT:"):
            subject = clean_line.split(":", 1)[1].strip()
            subject = subject.strip('"').strip("'").strip("*").strip()
        elif clean_line.upper().startswith("BODY:"):
            body_started = True
        elif body_started:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Fallback: if parsing failed, extract first line
    if not subject:
        if lines:
            first_line = lines[0].strip()
            if ":" in first_line:
                subject = first_line.split(":", 1)[1].strip()
            else:
                subject = first_line[:50]
            subject = subject.strip('"').strip("'").strip("*")
    if not body:
        body = response_text.strip()

    # Clean subject line to guarantee natural peer-to-peer styling
    marketing_prefixes = [
        "certified ", "sourcing ", "introducing ", "production for ",
        "reliable ", "premium ", "high quality ", "re: "
    ]
    sub_lower = subject.lower().strip()
    for pref in marketing_prefixes:
        if sub_lower.startswith(pref):
            subject = subject[len(pref):].strip()
            break

    # Trim to 5 words max if too long
    words = subject.split()
    if len(words) > 6:
        subject = " ".join(words[:5])

    return subject, body


def generate_email(lead: dict, email_type: str = "cold_intro",
                   previous_subject: str = "",
                   account: dict = None,
                   max_retries: int = 3) -> dict:
    """
    Generate a personalized email for a lead using Gemini AI.
    Returns dict with: subject, body, email_type, spam_check.
    """
    client = _get_client()
    product = _pick_product_context(lead.get("product_interest", ""))

    # Build the appropriate prompt with account persona awareness
    if email_type == "cold_intro":
        user_prompt = _build_cold_intro_prompt(lead, product, account=account)
    elif email_type.startswith("followup_"):
        followup_num = int(email_type.split("_")[1])
        user_prompt = _build_followup_prompt(lead, product, followup_num,
                                              previous_subject)
    else:
        user_prompt = _build_cold_intro_prompt(lead, product, account=account)

    system_prompt = _build_system_prompt(account=account)

    # Candidate models to try with automatic fallback (prioritize stable production models)
    models_to_try = [GEMINI_MODEL, "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.7-flash", "gemini-3.6-flash"]
    candidate_models = []
    for m in models_to_try:
        if m and m not in candidate_models:
            candidate_models.append(m)

    for attempt in range(max_retries):
        model_name = candidate_models[attempt % len(candidate_models)]
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.9 + random.uniform(-0.1, 0.1),
                    "max_output_tokens": 3000,
                },
            )

            subject, body = _parse_ai_response(response.text)

            if not subject or not body:
                logger.warning(f"Empty response from Gemini (attempt {attempt + 1})")
                continue

            # Run through spam guard
            spam_result = check_email(subject, body)

            if spam_result["verdict"] == "fail":
                logger.warning(
                    f"Email failed spam check (attempt {attempt + 1}): "
                    f"score={spam_result['total_score']}, "
                    f"issues={spam_result['issues'][:3]}"
                )
                # Try to sanitize
                subject, body = sanitize_email_content(subject, body)
                spam_result = check_email(subject, body)

                if spam_result["verdict"] == "fail" and attempt < max_retries - 1:
                    # Retry with modified prompt
                    time.sleep(1)
                    continue

            return {
                "subject": subject,
                "body": body,
                "email_type": email_type,
                "product": product["name"],
                "spam_check": spam_result,
                "success": True,
            }

        except Exception as e:
            logger.error(f"Gemini API error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                logger.info(f"Retrying in {wait}s...")
                time.sleep(wait)

    # All retries failed
    return {
        "subject": "",
        "body": "",
        "email_type": email_type,
        "product": "",
        "spam_check": {},
        "success": False,
        "error": "Failed to generate email after retries",
    }


def generate_batch(leads: list, email_type: str = "cold_intro",
                    delay_between: float = 2.0) -> list:
    """
    Generate emails for a batch of leads.
    Returns list of dicts with lead_id and generated email.
    """
    results = []
    for lead in leads:
        result = generate_email(lead, email_type)
        result["lead_id"] = lead["id"]
        result["lead_email"] = lead["email"]
        results.append(result)

        if result["success"]:
            logger.info(
                f"  ✓ Generated {email_type} for {lead['email']} "
                f"[spam_score={result['spam_check'].get('total_score', '?')}]"
            )
        else:
            logger.error(f"  ✗ Failed for {lead['email']}: {result.get('error', 'unknown')}")

        # Delay between API calls to respect rate limits
        time.sleep(delay_between + random.uniform(0, 1))

    return results
