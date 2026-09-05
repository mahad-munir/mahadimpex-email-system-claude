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


def _build_system_prompt() -> str:
    """Build the system prompt that instructs Gemini how to write emails."""
    company = _contexts.get("company_profile", {})
    strengths = company.get("key_strengths", [])
    why_pakistan = company.get("why_pakistan", [])

    return f"""You are writing business emails as {SENDER_NAME}, {SENDER_TITLE} at {COMPANY_NAME}.

ABOUT THE COMPANY:
- {COMPANY_NAME} is a {company.get('type', 'textile sourcing company')} based in {company.get('location', 'Faisalabad, Pakistan')}
- Specialization: {company.get('specialization', '')}
- Key strengths: {'; '.join(strengths[:3])}
- Why Pakistan: {'; '.join(why_pakistan[:3])}
- Website: {COMPANY_WEBSITE}

CRITICAL WRITING RULES:
1. Write like a real human professional — NOT like a marketing template or AI
2. Keep emails SHORT (80-150 words for cold intros, 50-100 for follow-ups)
3. Use natural, conversational business English — not overly polished or formal
4. Vary your sentence length naturally — mix short punchy sentences with longer ones
5. NEVER use these spam trigger words: free, guaranteed, limited time, act now, buy now, exclusive deal, hurry, urgent, special offer, no obligation, risk free, incredible, amazing, unbelievable, phenomenal
6. NEVER use ALL CAPS for emphasis
7. Use maximum 1 exclamation mark per email (preferably zero)
8. Do NOT include any HTML, bullet points, or heavy formatting — plain text only
9. Do NOT start with "I hope this email finds you well" or similar clichés
10. Make each email feel unique — vary greetings, openings, angles, and sign-offs
11. Be specific about products/capabilities relevant to the recipient
12. End with a soft, low-pressure call to action (ask a question, suggest a brief chat)
13. NEVER promise prices, discounts, or specific numbers unless given
14. Write in first person as {SENDER_NAME}
15. Sound confident but not pushy — helpful, knowledgeable, approachable

EMAIL SIGNATURE (always include at the very end):
{SENDER_NAME}
{SENDER_TITLE}
{COMPANY_NAME} — {COMPANY_TAGLINE}
{COMPANY_WEBSITE}
{COMPANY_PHONE}

COMPLIANCE (always include after signature):
{COMPANY_ADDRESS}
To stop receiving these emails, reply with "unsubscribe"."""


def _build_cold_intro_prompt(lead: dict, product: dict) -> str:
    """Build the prompt for a cold introduction email."""
    angles = _contexts.get("cold_intro_angles", [])
    angle = random.choice(angles) if angles else {
        "angle": "direct_sourcing",
        "theme": "Introduce direct sourcing",
        "hook": "",
    }

    greeting_styles = _contexts.get("greeting_styles", ["Hi {first_name},"])
    greeting = random.choice(greeting_styles)
    if lead.get("first_name"):
        greeting = greeting.format(first_name=lead["first_name"])
    else:
        greeting = greeting.replace(" {first_name}", "").replace("{first_name}", "there")

    return f"""Write a cold outreach email to a potential textile buyer.

RECIPIENT INFO:
- Company: {lead.get('company_name', 'their company')}
- Contact name: {lead.get('first_name', '')}
- Country: {lead.get('country', '')}
- Their likely interest: {lead.get('product_interest', product['name'])}

PRODUCT TO HIGHLIGHT:
- Product: {product['name']}
- Description: {product['description']}
- Unique selling point: {product['usp']}

EMAIL ANGLE: {angle['theme']}
OPENING HOOK IDEA: {angle['hook']}

START THE EMAIL WITH: {greeting}

REQUIREMENTS:
- 80-150 words maximum (excluding signature)
- One clear, relevant value proposition
- End with a soft question or low-pressure CTA
- Generate a compelling subject line (under 60 chars, no spam words, no ALL CAPS)
- Do NOT use any clichéd openings

FORMAT YOUR RESPONSE EXACTLY AS:
SUBJECT: [your subject line]
BODY:
[your email body including signature and compliance footer]"""


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
    greeting = random.choice(greeting_styles)
    if lead.get("first_name"):
        greeting = greeting.format(first_name=lead["first_name"])
    else:
        greeting = greeting.replace(" {first_name}", "").replace("{first_name}", "there")

    return f"""Write follow-up #{followup_num} to a textile buyer who hasn't replied.

RECIPIENT INFO:
- Company: {lead.get('company_name', 'their company')}
- Contact name: {lead.get('first_name', '')}
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
[email body including signature and compliance footer]"""


def _parse_ai_response(response_text: str) -> tuple:
    """Parse Gemini response into subject and body."""
    subject = ""
    body = ""

    lines = response_text.strip().split("\n")

    body_started = False
    body_lines = []

    for line in lines:
        if line.upper().startswith("SUBJECT:"):
            subject = line.split(":", 1)[1].strip()
            # Remove quotes if Gemini wrapped it
            subject = subject.strip('"').strip("'")
        elif line.upper().startswith("BODY:"):
            body_started = True
        elif body_started:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Fallback: if parsing failed, use the whole response
    if not subject:
        # Try to extract first line as subject
        if lines:
            subject = lines[0][:60]
    if not body:
        body = response_text.strip()

    return subject, body


def generate_email(lead: dict, email_type: str = "cold_intro",
                   previous_subject: str = "",
                   max_retries: int = 3) -> dict:
    """
    Generate a personalized email for a lead using Gemini AI.
    Returns dict with: subject, body, email_type, spam_check.
    """
    client = _get_client()
    product = _pick_product_context(lead.get("product_interest", ""))

    # Build the appropriate prompt
    if email_type == "cold_intro":
        user_prompt = _build_cold_intro_prompt(lead, product)
    elif email_type.startswith("followup_"):
        followup_num = int(email_type.split("_")[1])
        user_prompt = _build_followup_prompt(lead, product, followup_num,
                                              previous_subject)
    else:
        user_prompt = _build_cold_intro_prompt(lead, product)

    system_prompt = _build_system_prompt()

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": 0.9 + random.uniform(-0.1, 0.1),
                    "max_output_tokens": 800,
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

            # Ensure compliance footer is present
            if "unsubscribe" not in body.lower():
                body += get_unsubscribe_footer()

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
