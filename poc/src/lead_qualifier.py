"""
BANT lead qualification logic for Cynbit IntelliAssist.
"""
import re
import logging
from datetime import datetime
from typing import Optional

from src.schemas import ConversationTurn, LeadProfile
from src import llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BANT field detection helpers
# ---------------------------------------------------------------------------

_BUDGET_PATTERNS = [
    re.compile(r"(?:budget|spend|invest|cost|price|₹|rs\.?|inr|lakh|lakhs?|crore|crores?)", re.I),
    re.compile(r"(?:\d+\s*(?:lakh|lac|k|thousand|million|crore))", re.I),
    re.compile(r"(?:₹|rs\.?)\s*[\d,]+", re.I),
]

_TIMELINE_PATTERNS = [
    re.compile(r"(?:month|week|quarter|year|q[1-4]|asap|urgent|soon|by\s+\w+)", re.I),
    re.compile(r"(?:january|february|march|april|may|june|july|august|september|october|november|december)", re.I),
    re.compile(r"\d{4}", re.I),
]

_AUTHORITY_PATTERNS = [
    re.compile(r"(?:i\s+make|i\s+decide|final\s+decision|decision\s+maker)", re.I),
    re.compile(r"(?:i\s+am|i'm)\s+(?:the\s+)?(?:ceo|cto|coo|cfo|founder|co-founder|head|director|vp|vice\s+president|owner)", re.I),
    re.compile(r"(?:need\s+approval|get\s+approval|approve|sign.off|board|committee|manager\s+needs)", re.I),
]

_NAME_PATTERNS = [
    re.compile(r"(?:my\s+name\s+is|call\s+me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.I),
    re.compile(r"(?:this\s+is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", re.I),
    re.compile(r"(?:i\s+am|i'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)(?!\s+(?:building|looking|working|interested|trying|reaching|planning|writing|contacting))", re.I),
]

_COMPANY_PATTERNS = [
    re.compile(r"(?:from|work\s+(?:at|for)|company\s+is|our\s+company)\s+([A-Z][a-zA-Z\s]+(?:Ltd|Inc|Pvt|LLC|Technologies|Solutions|Services|Systems|Group|Clinics|Health)?)", re.I),
    re.compile(r"(?:company|firm|organisation|organization|startup)\s+(?:name\s+is\s+|called\s+)?([A-Z][a-zA-Z\s]+)", re.I),
]

_SERVICE_KEYWORDS = {
    "ai agent": ["AI Agents & Automation"],
    "automation": ["AI Agents & Automation"],
    "chatbot": ["AI Agents & Automation", "LLM Integration"],
    "llm": ["LLM Integration"],
    "rag": ["LLM Integration"],
    "software": ["Software Development"],
    "saas": ["Software Development"],
    "web app": ["Software Development"],
    "app development": ["Software Development"],
    "lead generation": ["Growth & Lead Generation"],
    "marketing": ["Growth & Lead Generation"],
    "seo": ["Growth & Lead Generation"],
    "crm": ["Growth & Lead Generation"],
    "bitelevate": ["BitElevate"],
    "learning": ["BitElevate"],
    "edtech": ["BitElevate"],
    "tenanteasy": ["TenantEase"],
    "property": ["TenantEase"],
    "tenant": ["TenantEase"],
    "revio": ["Revio"],
    "revenue intelligence": ["Revio"],
    "cynbit studio": ["Cynbit Studio"],
}

# Qualification questions in priority order
_QUALIFICATION_QUESTIONS = [
    ("name", "Great! I'd love to learn more about you. Could you share your name and the company you're representing?"),
    ("primary_need", "What specific challenge or goal is driving your interest in AI/automation right now?"),
    ("budget_range", "To make sure I can suggest the right solution, do you have a budget range in mind for this initiative?"),
    ("timeline", "What's your ideal timeline for getting this up and running?"),
    ("decision_authority", "And finally — who else is involved in evaluating and approving this kind of investment?"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_bant(conversation: list[ConversationTurn]) -> LeadProfile:
    """Extract BANT fields from conversation history and return a LeadProfile."""
    profile = LeadProfile(
        qualification_score=0,
        qualification_status="unqualified",
        next_action="gather_info",
    )

    # Combine all user messages for extraction
    user_text = " ".join(t.content for t in conversation if t.role == "user")

    profile.name = _extract_name(user_text)
    profile.company = _extract_company(user_text)
    profile.primary_need = _extract_need(user_text, conversation)
    profile.budget_range = _extract_budget(user_text)
    profile.timeline = _extract_timeline(user_text)
    profile.decision_authority = _extract_authority(user_text)
    profile.service_interest = _extract_service_interests(user_text)

    score = score_lead(profile)
    profile.qualification_score = score
    profile.qualification_status = _determine_status(score)
    profile.next_action = _determine_next_action(profile)

    return profile


def get_next_question(profile: LeadProfile) -> str:
    """Return the next BANT qualification question to ask."""
    for field, question in _QUALIFICATION_QUESTIONS:
        if field == "name" and (not profile.name or not profile.company):
            return question
        elif field == "primary_need" and not profile.primary_need:
            return question
        elif field == "budget_range" and not profile.budget_range:
            return question
        elif field == "timeline" and not profile.timeline:
            return question
        elif field == "decision_authority" and not profile.decision_authority:
            return question

    # All BANT fields collected
    return (
        "Thank you — I have all the information I need! I'll pass your details to the Cynbit team. "
        "Someone from opportunities@cynbit.in will be in touch within 24 hours. "
        "Is there anything else you'd like to know about Cynbit in the meantime?"
    )


def score_lead(profile: LeadProfile) -> int:
    """Calculate a 0–100 lead qualification score based on BANT completeness."""
    score = 0

    # Identity (15 pts)
    if profile.name:
        score += 8
    if profile.company:
        score += 7

    # Need (25 pts)
    if profile.primary_need:
        score += 25

    # Budget (25 pts)
    if profile.budget_range:
        budget_lower = profile.budget_range.lower()
        if any(kw in budget_lower for kw in ["lakh", "lac", "crore", "million"]):
            score += 25
        elif any(kw in budget_lower for kw in ["thousand", "k", "budget"]):
            score += 15
        else:
            score += 10

    # Authority (20 pts)
    if profile.decision_authority:
        authority_lower = profile.decision_authority.lower()
        if any(kw in authority_lower for kw in ["i am", "i'm", "sole", "final", "owner", "ceo", "founder"]):
            score += 20
        else:
            score += 10

    # Timeline (15 pts)
    if profile.timeline:
        timeline_lower = profile.timeline.lower()
        if any(kw in timeline_lower for kw in ["asap", "urgent", "immediately", "month", "week"]):
            score += 15
        elif any(kw in timeline_lower for kw in ["quarter", "q1", "q2", "q3", "q4", "year"]):
            score += 10
        else:
            score += 5

    return min(score, 100)


def format_lead_email(profile: LeadProfile) -> str:
    """Format a lead summary suitable for email notification to the Cynbit team."""
    lines = [
        "🎯 New Lead from Cynbit IntelliAssist",
        "=" * 50,
        f"Collected at: {profile.collected_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "📋 LEAD PROFILE",
        f"  Name:               {profile.name or 'Not provided'}",
        f"  Company:            {profile.company or 'Not provided'}",
        "",
        "🔍 BANT QUALIFICATION",
        f"  Budget Range:       {profile.budget_range or 'Not disclosed'}",
        f"  Decision Authority: {profile.decision_authority or 'Not identified'}",
        f"  Primary Need:       {profile.primary_need or 'Not specified'}",
        f"  Timeline:           {profile.timeline or 'Not specified'}",
        "",
        "🏷️  Service Interest:",
    ]

    if profile.service_interest:
        for svc in profile.service_interest:
            lines.append(f"    - {svc}")
    else:
        lines.append("    - Not specified")

    lines += [
        "",
        f"📊 QUALIFICATION SCORE: {profile.qualification_score}/100 ({profile.qualification_status.upper()})",
        f"   Next Action: {profile.next_action}",
        "",
        "=" * 50,
        "Reply to this lead at opportunities@cynbit.in",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_EXCLUDED_NAMES = {
    "building", "looking", "interested", "trying", "working",
    "planning", "writing", "contacting", "reaching", "the", "a", "an", "here"
}

def _extract_name(text: str) -> Optional[str]:
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = match.group(1).strip().title()
            first_word = candidate.split()[0].lower()
            if first_word not in _EXCLUDED_NAMES and len(candidate) > 2:
                return candidate
    return None


def _extract_company(text: str) -> Optional[str]:
    for pattern in _COMPANY_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip()
            if 3 < len(name) < 60:
                return name
    return None


def _extract_need(text: str, conversation: list[ConversationTurn]) -> Optional[str]:
    """Extract the primary need from the longest user utterance."""
    user_turns = [t.content for t in conversation if t.role == "user"]
    if not user_turns:
        return None
    longest = max(user_turns, key=len)
    low = longest.lower()
    if any(phrase in low for phrase in ["not sure yet", "just exploring", "just browsing", "no specific need"]):
        return None
    if len(longest) > 20 and any(kw in low for kw in ["need", "want", "looking for", "build", "require", "develop", "system", "automation", "agent", "app"]):
        return longest[:300]
    return None


def _extract_budget(text: str) -> Optional[str]:
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            # Extract surrounding context (budget phrase)
            start = max(0, match.start() - 10)
            end = min(len(text), match.end() + 30)
            return text[start:end].strip()
    return None


def _extract_timeline(text: str) -> Optional[str]:
    for pattern in _TIMELINE_PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 5)
            end = min(len(text), match.end() + 20)
            return text[start:end].strip()
    return None


def _extract_authority(text: str) -> Optional[str]:
    for pattern in _AUTHORITY_PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 5)
            end = min(len(text), match.end() + 30)
            return text[start:end].strip()
    return None


def _extract_service_interests(text: str) -> list[str]:
    text_lower = text.lower()
    interests: list[str] = []
    for keyword, services in _SERVICE_KEYWORDS.items():
        if keyword in text_lower:
            for svc in services:
                if svc not in interests:
                    interests.append(svc)
    return interests


def _determine_status(score: int) -> str:
    if score >= 70:
        return "hot"
    elif score >= 40:
        return "warm"
    elif score >= 10:
        return "cold"
    return "unqualified"


def _determine_next_action(profile: LeadProfile) -> str:
    if profile.qualification_status == "hot":
        return "Schedule discovery call immediately. Contact within 2 hours."
    elif profile.qualification_status == "warm":
        return "Send detailed service overview. Follow up within 24 hours."
    elif profile.qualification_status == "cold":
        return "Add to nurture sequence. Monthly follow-up."
    return "Continue qualification conversation to gather BANT information."

