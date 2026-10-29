"""
Provider-agnostic LLM wrapper for Cynbit IntelliAssist.
Supports: gemini, openai, demo (no API key required).
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo-mode canned responses keyed by keyword patterns
# ---------------------------------------------------------------------------
DEMO_RESPONSES: dict[str, str] = {
    "services": (
        "Cynbit Technologies offers three core service lines:\n\n"
        "1. **AI Agents & Automation** – Design and deployment of autonomous LLM-powered agents for customer support, "
        "sales qualification, document processing, and multi-step workflow orchestration.\n\n"
        "2. **Software Development** – Full-stack SaaS products, web apps, and API-first architectures built with "
        "React, Next.js, FastAPI, and PostgreSQL. MVPs typically delivered in 6–12 weeks.\n\n"
        "3. **Growth & Lead Generation** – AI-augmented paid advertising, SEO, CRM automation, and conversion funnel "
        "optimisation with a focus on measurable ROI.\n\n"
        "All services are backed by Cynbit's 'Engineering for Optimism' philosophy — building technology that creates "
        "genuine business and social value. To discuss your specific needs, email opportunities@cynbit.in."
    ),
    "bitelevate": (
        "BitElevate is Cynbit's flagship EdTech product — an adaptive learning platform that personalises education "
        "across **16+ cognitive and learning-style dimensions**. The AI engine assesses each student's learning pace, "
        "comprehension patterns, and preferred content formats, then dynamically adjusts the curriculum in real time.\n\n"
        "A key differentiator is BitElevate's commitment to **digital inclusion**: it functions effectively on "
        "low-bandwidth connections and supports regional language interfaces. Through a partnership with the "
        "**Manav Seva Trust**, BitElevate has been deployed in pilot programmes across Rajasthan, bringing "
        "AI-powered tutoring to underserved student communities."
    ),
    "tenanteasy": (
        "TenantEase is Cynbit's property management SaaS platform, purpose-built for the Indian real estate market. "
        "It automates the entire tenant lifecycle:\n\n"
        "- **Onboarding** – Digital lease agreements, KYC verification\n"
        "- **Rent Collection** – UPI-integrated automated reminders and receipts\n"
        "- **Maintenance** – Request tracking with AI-driven priority scoring\n"
        "- **Communication** – WhatsApp-native tenant messaging\n\n"
        "TenantEase originated as a client project for a Jaipur co-living operator managing 200+ units and was "
        "subsequently productised. It supports GST-compliant invoicing and targets individual landlords through "
        "mid-size property management firms."
    ),
    "team": (
        "Cynbit was co-founded in April 2024 and is led by:\n\n"
        "- **Mohak Saini** – CEO & Co-founder: drives strategic vision, client relationships, and product direction.\n"
        "- **Ashutosh Upadhyay** – Co-founder: leads product strategy and go-to-market execution.\n"
        "- **Dhawan Kumar Nama** – CTO: oversees engineering architecture, AI/ML systems, and technical delivery.\n\n"
        "The broader team comprises ~15 engineers, designers, and growth strategists based primarily in Jaipur, Rajasthan."
    ),
    "contact": (
        "You can reach Cynbit Technologies through the following channels:\n\n"
        "- 📧 **Business & Partnerships:** opportunities@cynbit.in\n"
        "- 🛠️ **Technical Support:** support@cynbit.in\n"
        "- 📞 **Phone:** +91 89479 62667 (Mon–Fri, 10 AM – 7 PM IST)\n"
        "- 📍 **Office:** Jaipur, Rajasthan, India\n\n"
        "The team typically responds to email inquiries within 24 business hours. "
        "To start a project conversation, email opportunities@cynbit.in with a brief description of your needs."
    ),
    "pricing": (
        "Cynbit offers four flexible engagement models:\n\n"
        "1. **Project-based** – Fixed scope & price, ideal for MVPs. Starting from ₹2 Lakhs.\n"
        "2. **Dedicated Team** – A pod of 2–5 engineers embedded with your team, billed monthly.\n"
        "3. **Retainer** – Monthly AI strategy, audits, and continuous improvement. From ₹75,000/month.\n"
        "4. **POC/Pilot** – 2–4 week proof-of-concept to validate AI use cases before full investment.\n\n"
        "All pricing is custom-quoted based on complexity, team size, and timeline. "
        "Reach out to opportunities@cynbit.in for a tailored proposal."
    ),
    "about": (
        "Cynbit Technologies is an AI-first technology company founded in **April 2024** in **Jaipur, Rajasthan, India**. "
        "Operating under the philosophy of **'Engineering for Optimism'**, the company believes that thoughtfully built "
        "technology can solve real human problems and create positive societal impact.\n\n"
        "With a team of ~15 specialists, Cynbit builds AI-powered products (BitElevate, TenantEase, Cynbit Studio, Revio) "
        "and delivers AI/automation services to startups and mid-market businesses across India and globally."
    ),
    "revio": (
        "Revio is Cynbit's revenue intelligence platform designed for sales teams and growth leaders. It aggregates data "
        "from CRMs, marketing platforms, and customer touchpoints to provide a unified revenue funnel view.\n\n"
        "Key capabilities:\n"
        "- AI-powered lead scoring and deal risk identification\n"
        "- Pipeline forecasting and next-best-action recommendations\n"
        "- Meeting intelligence via call transcript analysis\n"
        "- Automated CRM data enrichment\n\n"
        "Revio integrates with HubSpot, Salesforce, Pipedrive, and custom CRMs via its API-first architecture."
    ),
    "cynbit studio": (
        "Cynbit Studio is a no-code/low-code AI agent builder that enables non-technical teams to design, test, and "
        "deploy AI agents without deep engineering expertise. Users can:\n\n"
        "- Visually compose agent workflows with drag-and-drop nodes\n"
        "- Connect data sources (documents, databases, APIs)\n"
        "- Configure LLM settings and prompt templates\n"
        "- Publish agents as embeddable chat widgets or REST API endpoints\n\n"
        "Studio abstracts away RAG pipeline complexity, prompt engineering, and LLM API management."
    ),
    "default": (
        "Based on Cynbit's knowledge base, I can help you with information about Cynbit Technologies' services "
        "(AI agents, software development, growth/lead generation), products (BitElevate, TenantEase, Cynbit Studio, "
        "Revio), team, pricing, and contact details.\n\n"
        "Could you clarify what specific aspect of Cynbit you'd like to know more about? "
        "Alternatively, for direct assistance, contact the team at opportunities@cynbit.in or call +91 89479 62667."
    ),
}

DEMO_STRUCTURED: dict[str, dict] = {
    "lead_extraction": {
        "name": None,
        "company": None,
        "budget_range": None,
        "decision_authority": None,
        "primary_need": None,
        "timeline": None,
        "service_interest": [],
        "qualification_score": 0,
        "qualification_status": "unqualified",
        "next_action": "Ask for the prospect's name and company to get started.",
    }
}


def _is_demo_mode() -> bool:
    """Return True when DEMO_MODE env is set or no API key is available."""
    if os.getenv("DEMO_MODE", "").lower() in ("true", "1", "yes"):
        return True
    provider = os.getenv("LLM_PROVIDER", "demo").lower()
    if provider == "demo":
        return True
    if provider == "gemini" and not os.getenv("GEMINI_API_KEY"):
        return True
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        return True
    return False


def _demo_generate(prompt: str) -> str:
    """Return a realistic canned response based on keyword matching."""
    prompt_lower = prompt.lower()
    for keyword, response in DEMO_RESPONSES.items():
        if keyword in prompt_lower:
            return response
    return DEMO_RESPONSES["default"]


def _demo_generate_structured(schema: dict) -> dict:
    """Return a valid demo dict matching the given schema keys."""
    schema_title = schema.get("title", "")
    if "lead" in schema_title.lower():
        return DEMO_STRUCTURED["lead_extraction"].copy()
    # Generic fallback: return empty-string values for string fields
    result = {}
    for prop, defn in schema.get("properties", {}).items():
        t = defn.get("type", "string")
        if t == "string":
            result[prop] = ""
        elif t == "integer":
            result[prop] = 0
        elif t == "array":
            result[prop] = []
        elif t == "boolean":
            result[prop] = False
        else:
            result[prop] = None
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DEMO_MODE: bool = _is_demo_mode()


def generate(
    prompt: str,
    system: Optional[str] = None,
    temperature: float = 0.1,
) -> str:
    """Generate a text response from the configured LLM provider.

    Falls back to DEMO_MODE (cached, realistic responses) when no API key
    is present, so the application works without any credentials.
    """
    if DEMO_MODE:
        logger.debug("DEMO_MODE: returning canned response.")
        return _demo_generate(prompt)

    provider = os.getenv("LLM_PROVIDER", "demo").lower()

    if provider == "gemini":
        return _gemini_generate(prompt, system, temperature)
    elif provider == "openai":
        return _openai_generate(prompt, system, temperature)
    else:
        return _demo_generate(prompt)


def generate_structured(
    prompt: str,
    schema: dict,
    system: Optional[str] = None,
) -> dict:
    """Generate a structured (JSON) response validated against `schema`.

    In DEMO_MODE returns a pre-built dict matching the schema shape.
    """
    if DEMO_MODE:
        logger.debug("DEMO_MODE: returning canned structured response.")
        return _demo_generate_structured(schema)

    provider = os.getenv("LLM_PROVIDER", "demo").lower()

    if provider == "gemini":
        raw = _gemini_generate(
            prompt=f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}",
            system=system,
            temperature=0.0,
        )
    elif provider == "openai":
        raw = _openai_generate(
            prompt=f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}",
            system=system,
            temperature=0.0,
        )
    else:
        return _demo_generate_structured(schema)

    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON; falling back to demo structured response.")
        return _demo_generate_structured(schema)


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

def _gemini_generate(prompt: str, system: Optional[str], temperature: float) -> str:
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system or "",
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=temperature),
        )
        return response.text
    except Exception as exc:
        logger.error("Gemini generation failed: %s. Falling back to demo.", exc)
        return _demo_generate(prompt)


def _openai_generate(prompt: str, system: Optional[str], temperature: float) -> str:
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as exc:
        logger.error("OpenAI generation failed: %s. Falling back to demo.", exc)
        return _demo_generate(prompt)

