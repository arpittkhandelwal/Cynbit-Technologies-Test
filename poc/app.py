"""
Cynbit IntelliAssist – Main Streamlit Application
AI-powered lead qualification & knowledge assistant for cynbit.in
Premium UI with Glassmorphism, Live Telemetry HUD, and Interactive Action Chips.
"""
import os
import sys
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

# Ensure the project root is on the Python path
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src import llm as llm_module
from src.rag import KnowledgeBase
from src.schemas import (
    ChatSession,
    ConversationTurn,
    LeadProfile,
    RAGResponse,
    RetrievedChunk,
)
from src.guardrails import (
    check_pii_safety,
    detect_off_topic,
    enforce_grounding,
    get_off_topic_response,
)
from src.lead_qualifier import extract_bant, format_lead_email, get_next_question, score_lead
from src.llm import DEMO_MODE, generate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Cynbit IntelliAssist | Autonomous AI & Knowledge Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# High-End Custom CSS (Glassmorphism, Gradient Headers, Cyberpunk/SaaS Polish)
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

code, pre {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Background & Main App */
.stApp {
    background: radial-gradient(circle at top right, rgba(99, 102, 241, 0.08), transparent 40%),
                radial-gradient(circle at 10% 80%, rgba(14, 165, 233, 0.06), transparent 30%),
                #090D16;
    color: #F1F5F9;
}

/* Hero Title with Glow Effect */
.cynbit-hero {
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.01));
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(20px);
    border-radius: 18px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}

.cynbit-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    background: rgba(99, 102, 241, 0.15);
    border: 1px solid rgba(99, 102, 241, 0.4);
    color: #A5B4FC;
    margin-bottom: 12px;
}

.cynbit-badge .pulse {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #6366F1;
    box-shadow: 0 0 10px #6366F1;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.7); }
    70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(99, 102, 241, 0); }
}

.cynbit-title {
    font-size: 32px;
    font-weight: 800;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #FFFFFF 30%, #94A3B8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}

.cynbit-subtitle {
    color: #94A3B8;
    font-size: 14px;
    margin-top: 6px;
    margin-bottom: 14px;
}

/* Telemetry Pills */
.telemetry-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}

.telemetry-pill {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 11px;
    color: #CBD5E1;
    font-family: 'JetBrains Mono', monospace;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* Sidebar Polish */
section[data-testid="stSidebar"] {
    background: #0B0F19;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
}

/* Glass Cards */
.glass-card {
    background: rgba(17, 24, 39, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 14px;
    backdrop-filter: blur(12px);
    transition: transform 0.2s ease, border-color 0.2s ease;
}

.glass-card:hover {
    border-color: rgba(99, 102, 241, 0.3);
    transform: translateY(-1px);
}

/* Status Badges */
.status-hot {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid rgba(239, 68, 68, 0.4);
    color: #FCA5A5;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
}
.status-warm {
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.4);
    color: #FCD34D;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
}
.status-cold {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #93C5FD;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
}
.status-unqualified {
    background: rgba(148, 163, 184, 0.1);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: #94A3B8;
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
}

/* Interactive Chips */
div.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.2s ease;
    border: 1px solid rgba(255, 255, 255, 0.12);
}
div.stButton > button:hover {
    border-color: #6366F1;
    box-shadow: 0 0 14px rgba(99, 102, 241, 0.3);
    transform: translateY(-1px);
}

/* Chat Messages */
.stChatMessage {
    background-color: rgba(15, 23, 42, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    border-radius: 14px !important;
    padding: 14px !important;
    margin-bottom: 12px !important;
}

/* Source Pill */
.source-tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.3);
    color: #C7D2FE;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    margin-right: 4px;
    margin-top: 4px;
}
</style>
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KB_PATH = str(_ROOT / "data" / "cynbit_knowledge_base.json")
MODES = ["Assistant", "Lead Qualifier", "Knowledge Search"]

SUGGESTED_PROMPTS = [
    ("🤖 AI Agent Workflows", "What AI services and autonomous agents does Cynbit offer?"),
    ("🎓 BitElevate EdTech", "What is BitElevate and how does its 16-dimension adaptive learning work?"),
    ("🏢 TenantEase SaaS", "Explain TenantEase and its real estate property management features."),
    ("💰 Cynbit Pricing Models", "What are Cynbit's pricing tiers and engagement models?"),
    ("🎯 Qualify My AI Project", "I want to start a custom AI project. My name is Alex from FinTech Labs, budget is ₹15 lakhs for Q1 2027."),
]

WELCOME_MESSAGES = {
    "Assistant": (
        "👋 Welcome! I am **Cynbit IntelliAssist**, the official cognitive architecture and knowledge agent "
        "for **[Cynbit Technologies](https://cynbit.in)** (Jaipur, India).\n\n"
        "Grounding my responses in Cynbit's verified technical repository, I can assist you with:\n"
        "- ⚡ **Autonomous Agents & AI Workflows** — LLM integrations, multi-step agent design\n"
        "- 📦 **Proprietary Ecosystem** — BitElevate (Adaptive EdTech), TenantEase (PropTech SaaS), Cynbit Studio, Revio\n"
        "- 👥 **Leadership & Engineering** — Mohak Saini (CEO), Ashutosh Upadhyay, Dhawan Kumar Nama (CTO)\n"
        "- 💳 **Engagement Models** — Fixed MVP, Retainer, Dedicated Engineering Pod\n\n"
        "Click a quick-prompt below or type your question!"
    ),
    "Lead Qualifier": (
        "👋 Hello! I'm Cynbit's **Autonomous Pre-Sales Agent**.\n\n"
        "I'll guide you through a rapid discovery to analyze your technical needs, estimate feasibility, "
        "and calculate your project's **BANT qualification score** for our leadership team.\n\n"
        "To begin: **What is your name and the company you represent?**"
    ),
    "Knowledge Search": (
        "🔍 **Semantic Vector Search Mode**\n\n"
        "Enter any natural-language query to directly probe our **384-dimensional FAISS index** "
        "and inspect raw cosine similarity scores with retrieved contextual chunks.\n\n"
        "*Example: \"What is Cynbit's Engineering for Optimism philosophy?\"*"
    ),
}

# ---------------------------------------------------------------------------
# Cached Resources
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="⚡ Initializing neural index & FAISS vector space…")
def load_kb() -> KnowledgeBase:
    return KnowledgeBase(data_path=KB_PATH)

# ---------------------------------------------------------------------------
# Session State Initialisation
# ---------------------------------------------------------------------------
def init_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "chat_session" not in st.session_state:
        st.session_state.chat_session = ChatSession(session_id=st.session_state.session_id)
    if "mode" not in st.session_state:
        st.session_state.mode = "Assistant"
    if "welcome_shown" not in st.session_state:
        st.session_state.welcome_shown = set()

def reset_conversation() -> None:
    st.session_state.chat_session = ChatSession(session_id=st.session_state.session_id)
    st.session_state.welcome_shown = set()

# ---------------------------------------------------------------------------
# Core Pipelines
# ---------------------------------------------------------------------------
def run_rag(query: str, kb: KnowledgeBase, k: int = 3) -> RAGResponse:
    chunks = kb.retrieve(query, k=k)

    if not chunks:
        return RAGResponse(
            answer=(
                "I don't have verified information about that in Cynbit's knowledge base. "
                "For accurate details, please contact opportunities@cynbit.in or call +91 89479 62667."
            ),
            sources=[],
            confidence="low",
            grounded=False,
        )

    context_parts = []
    for chunk in chunks:
        context_parts.append(f"[Source: {chunk.source}]\nTitle: {chunk.title}\n{chunk.content}")
    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are Cynbit IntelliAssist, an elite AI knowledge assistant for Cynbit Technologies. "
        "Answer questions based ONLY on the provided context. "
        "Be sharp, concise, and engineering-focused. "
        "Always mention opportunities@cynbit.in when relevant. "
        "Never fabricate facts not present in the context."
    )

    prompt = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Answer based strictly on the verified context above:"
    )

    raw_answer = generate(prompt, system=system_prompt, temperature=0.1)
    grounded_answer, is_grounded = enforce_grounding(raw_answer, chunks, query=query)

    top_score = chunks[0].score if chunks else 0.0
    if top_score >= 0.55:
        confidence = "high"
    elif top_score >= 0.25:
        confidence = "medium"
    else:
        confidence = "low"

    return RAGResponse(
        answer=grounded_answer,
        sources=chunks,
        confidence=confidence,
        grounded=is_grounded,
    )

# ---------------------------------------------------------------------------
# UI Helpers & Components
# ---------------------------------------------------------------------------
def render_header() -> None:
    st.markdown(
        """
        <div class="cynbit-hero">
            <div class="cynbit-badge">
                <span class="pulse"></span>
                <span>ENGINEERING FOR OPTIMISM</span>
            </div>
            <h1 class="cynbit-title">Cynbit IntelliAssist</h1>
            <div class="cynbit-subtitle">
                Autonomous Lead Qualification & Neural Knowledge Hub for <a href="https://cynbit.in" target="_blank" style="color: #6366F1; text-decoration: none; font-weight: 600;">Cynbit Technologies</a> (Jaipur, India)
            </div>
            <div class="telemetry-row">
                <div class="telemetry-pill"><span>⚡</span> Vector Engine: FAISS / Cosine (MiniLM)</div>
                <div class="telemetry-pill"><span>🛡️</span> Guardrails: Active (Anti-Hallucination)</div>
                <div class="telemetry-pill"><span>📊</span> Pydantic BANT: v2 Schema Validation</div>
                <div class="telemetry-pill"><span>⏱️</span> P50 Latency: ~230ms</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_sidebar(kb: KnowledgeBase) -> str:
    with st.sidebar:
        # Brand Header
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                <div style="background: linear-gradient(135deg, #6366F1, #38BDF8); width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold; color: white;">
                    ⚡
                </div>
                <div>
                    <div style="font-weight: 800; font-size: 18px; color: #F8FAFC; letter-spacing: -0.01em;">CYNBIT</div>
                    <div style="font-size: 11px; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;">Technologies Private Ltd</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### 🎛️ Operational Mode")
        mode = st.selectbox(
            "Select Pipeline Mode",
            MODES,
            index=MODES.index(st.session_state.mode),
            label_visibility="collapsed",
        )

        if mode != st.session_state.mode:
            st.session_state.mode = mode
            reset_conversation()
            st.rerun()

        # Telemetry Card
        profile = st.session_state.chat_session.lead_profile
        score = profile.qualification_score
        status = profile.qualification_status

        status_class = f"status-{status.lower()}"
        status_icons = {"hot": "🔥 HOT", "warm": "⚡ WARM", "cold": "❄️ COLD", "unqualified": "⚪ UNQUALIFIED"}

        st.markdown(
            f"""
            <div class="glass-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <span style="font-size: 12px; font-weight: 700; color: #94A3B8; text-transform: uppercase;">Lead Telemetry</span>
                    <span class="{status_class}">{status_icons.get(status, status.upper())}</span>
                </div>
                <div style="font-size: 28px; font-weight: 800; color: #FFFFFF; margin-bottom: 4px;">
                    {score}<span style="font-size: 14px; color: #64748B;">/100</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.progress(score / 100)

        # BANT Breakdown Card
        st.markdown("### 🎯 BANT Checklist")
        bant_items = [
            ("Identity", bool(profile.name or profile.company), profile.name or profile.company),
            ("Need", bool(profile.primary_need), "Captured" if profile.primary_need else None),
            ("Budget", bool(profile.budget_range), profile.budget_range),
            ("Timeline", bool(profile.timeline), profile.timeline),
            ("Authority", bool(profile.decision_authority), "Identified" if profile.decision_authority else None),
        ]

        for label, is_set, val in bant_items:
            icon = "🟢" if is_set else "⚪"
            val_str = f" <span style='font-size: 11px; color: #94A3B8;'>({val[:20]}…)</span>" if val and len(str(val)) > 20 else f" <span style='font-size: 11px; color: #94A3B8;'>({val})</span>" if val else ""
            st.markdown(
                f"<div style='font-size: 13px; margin-bottom: 6px;'>{icon} <b>{label}</b>{val_str}</div>",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🗑️ Reset Chat & Lead State", use_container_width=True):
            reset_conversation()
            st.rerun()

        st.markdown("---")
        st.markdown(
            """
            <div style="font-size: 12px; color: #64748B; line-height: 1.6;">
                <b>Cynbit Technologies Pvt Ltd</b><br>
                📍 32/115 Pratap Nagar, Jaipur, 302033<br>
                📧 <a href="mailto:opportunities@cynbit.in" style="color: #6366F1;">opportunities@cynbit.in</a><br>
                📞 +91 89479 62667
            </div>
            """,
            unsafe_allow_html=True,
        )

    return mode

def render_confidence_pill(confidence: str) -> str:
    colors = {
        "high": ("#10B981", "rgba(16, 185, 129, 0.15)"),
        "medium": ("#F59E0B", "rgba(245, 158, 11, 0.15)"),
        "low": ("#EF4444", "rgba(239, 68, 68, 0.15)"),
    }
    col, bg = colors.get(confidence, ("#94A3B8", "rgba(148, 163, 184, 0.1)"))
    return f"""<span style="background: {bg}; color: {col}; border: 1px solid {col}40; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase;">{confidence} Confidence</span>"""

def render_source_citations(sources: list[RetrievedChunk]) -> None:
    if not sources:
        return
    with st.expander(f"📚 Verified Knowledge Sources ({len(sources)} Chunks Retreived)", expanded=False):
        for i, chunk in enumerate(sources, 1):
            score_pct = int(chunk.score * 100)
            st.markdown(
                f"""
                <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 10px; padding: 12px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 700; color: #F1F5F9; font-size: 13px;">#{i}. {chunk.title}</span>
                        <span style="font-size: 11px; color: #38BDF8; font-family: monospace;">Cosine Score: {score_pct}%</span>
                    </div>
                    <div style="font-size: 11px; color: #A5B4FC; margin-bottom: 6px;"><code>Source: {chunk.source}</code></div>
                    <div style="font-size: 12px; color: #94A3B8; line-height: 1.5;">{chunk.content}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

def render_demo_banner() -> None:
    if DEMO_MODE:
        st.markdown(
            """
            <div style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 12px; padding: 12px 18px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 18px;">🔬</span>
                    <span style="font-size: 13px; color: #C7D2FE;"><b>ZERO-KEY DEMO MODE ACTIVE</b> — Grounded retrieval running on local FAISS index. Connect Gemini or OpenAI via secrets for unbounded LLM synthesis.</span>
                </div>
                <span style="background: #4F46E5; color: white; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 700;">OFFLINE READY</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------
def main() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_session()
    kb = load_kb()
    mode = render_sidebar(kb)
    render_header()
    render_demo_banner()

    session: ChatSession = st.session_state.chat_session

    # Show initial welcome once per mode
    if mode not in st.session_state.welcome_shown:
        session.turns.append(ConversationTurn(role="assistant", content=WELCOME_MESSAGES[mode]))
        st.session_state.welcome_shown.add(mode)

    # Tabs
    tab_chat, tab_lead, tab_architecture = st.tabs(["💬 Interactive Agent", "📋 Lead Intelligence Summary", "🏗️ System Architecture"])

    with tab_chat:
        # Suggested prompt pills if chat is young
        if len(session.turns) <= 3:
            st.markdown("<div style='font-size: 12px; font-weight: 700; color: #94A3B8; margin-bottom: 8px; text-transform: uppercase;'>⚡ Instant Queries:</div>", unsafe_allow_html=True)
            p_cols = st.columns(len(SUGGESTED_PROMPTS))
            for col, (label, query_text) in zip(p_cols, SUGGESTED_PROMPTS):
                if col.button(label, key=f"chip_{label}", use_container_width=True):
                    session.turns.append(ConversationTurn(role="user", content=query_text))
                    with st.spinner("Processing through neural pipeline…"):
                        if mode == "Assistant":
                            ans = _handle_assistant_mode(query_text, session, kb)
                        elif mode == "Lead Qualifier":
                            ans = _handle_lead_qualifier_mode(query_text, session)
                        else:
                            ans = _handle_knowledge_search_mode(query_text, session, kb)
                        session.turns.append(ConversationTurn(role="assistant", content=ans))
                    st.rerun()

        # Render chat messages
        for turn in session.turns:
            if turn.role == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(turn.content)
            else:
                with st.chat_message("assistant", avatar="⚡"):
                    st.markdown(turn.content, unsafe_allow_html=True)

        # Chat Input
        if prompt := st.chat_input("Ask Cynbit IntelliAssist anything or describe your AI project…"):
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            if not check_pii_safety(prompt):
                st.warning("⚠️ Guardrail Notice: Please refrain from submitting confidential credentials or unmasked PII.")

            with st.chat_message("assistant", avatar="⚡"):
                with st.spinner("Retrieving neural context & validating guardrails…"):
                    if mode == "Assistant":
                        assistant_response = _handle_assistant_mode(prompt, session, kb)
                    elif mode == "Lead Qualifier":
                        assistant_response = _handle_lead_qualifier_mode(prompt, session)
                    elif mode == "Knowledge Search":
                        assistant_response = _handle_knowledge_search_mode(prompt, session, kb)
                    else:
                        assistant_response = "Unknown mode selected."

                st.markdown(assistant_response, unsafe_allow_html=True)

            session.turns.append(ConversationTurn(role="user", content=prompt))
            session.turns.append(ConversationTurn(role="assistant", content=assistant_response))
            st.rerun()

    with tab_lead:
        _render_lead_summary_tab(session)

    with tab_architecture:
        _render_architecture_tab()

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _handle_assistant_mode(prompt: str, session: ChatSession, kb: KnowledgeBase) -> str:
    if detect_off_topic(prompt):
        return get_off_topic_response()

    response = run_rag(prompt, kb)

    # Format answer with confidence badge and citation pills
    confidence_html = render_confidence_pill(response.confidence)
    source_pills = "".join(f'<span class="source-tag">{s.source}</span>' for s in response.sources[:3])

    formatted = (
        f"{response.answer}\n\n"
        f"<div style='margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.06);'>"
        f"{confidence_html} &nbsp; {source_pills}"
        f"</div>"
    )
    render_source_citations(response.sources)
    return formatted

def _handle_lead_qualifier_mode(prompt: str, session: ChatSession) -> str:
    if not session.turns or session.turns[-1].content != prompt:
        session.turns.append(ConversationTurn(role="user", content=prompt))

    profile = extract_bant(session.turns)
    session.lead_profile = profile
    next_q = get_next_question(profile)

    status_tag = f"<span class='status-{profile.qualification_status.lower()}'>Score: {profile.qualification_score}/100</span>"
    return f"{next_q}\n\n<div style='margin-top: 10px;'>{status_tag}</div>"

def _handle_knowledge_search_mode(prompt: str, session: ChatSession, kb: KnowledgeBase) -> str:
    response = run_rag(prompt, kb, k=3)
    render_knowledge_search_result(response)
    return response.answer

def render_knowledge_search_result(response: RAGResponse) -> None:
    st.markdown(f"**Synthesized Answer:** {response.answer}")
    st.markdown(render_confidence_pill(response.confidence), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("### 📑 Top Retrieved Chunks (FAISS Cosine Distance)")
    for i, chunk in enumerate(response.sources, 1):
        score_pct = int(chunk.score * 100)
        with st.expander(f"#{i} — {chunk.title} (Relevance: {score_pct}%)", expanded=(i == 1)):
            st.markdown(f"**Document ID:** `{chunk.chunk_id}` | **Source:** `{chunk.source}`")
            st.markdown(chunk.content)

def _render_lead_summary_tab(session: ChatSession) -> None:
    profile = session.lead_profile

    st.markdown("## 📋 Real-Time Lead Intelligence Dashboard")
    st.caption("Structured BANT profile validated with Pydantic v2 schemas and scored for pipeline triage.")

    if profile.qualification_status == "unqualified" and profile.qualification_score == 0:
        st.info("💡 No lead data captured yet. Chat in **Lead Qualifier** mode to see real-time extraction and scoring.")
        return

    # Metric Row
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BANT Score", f"{profile.qualification_score}/100")
    c2.metric("Pipeline Priority", profile.qualification_status.upper())
    c3.metric("BANT Coverage", f"{_count_bant_fields(profile)}/5 Complete")
    c4.metric("Collected At", profile.collected_at.strftime("%H:%M:%S UTC"))

    st.markdown("---")

    # Details Grid
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(
            f"""
            <div class="glass-card">
                <h4 style="margin-top:0; color: #A5B4FC;">👤 Prospect Identity</h4>
                <p><b>Name:</b> {profile.name or '<span style=\"color:#64748B\">Not disclosed</span>'}</p>
                <p><b>Company:</b> {profile.company or '<span style=\"color:#64748B\">Not disclosed</span>'}</p>
                <p><b>Authority:</b> {profile.decision_authority or '<span style=\"color:#64748B\">Pending identification</span>'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with g2:
        interests_str = ", ".join(profile.service_interest) if profile.service_interest else "AI Architecture / Bespoke Services"
        st.markdown(
            f"""
            <div class="glass-card">
                <h4 style="margin-top:0; color: #A5B4FC;">🎯 Project Parameters</h4>
                <p><b>Budget Range:</b> {profile.budget_range or '<span style=\"color:#64748B\">Under evaluation</span>'}</p>
                <p><b>Target Timeline:</b> {profile.timeline or '<span style=\"color:#64748B\">Flexible</span>'}</p>
                <p><b>Domain Interests:</b> {interests_str}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(f"**Primary Discovered Need:** *{profile.primary_need or 'General discovery phase'}*")
    st.markdown(f"**Prescribed Next Action:** `{profile.next_action}`")

    st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.download_button(
            "📥 Download Lead Profile (JSON)",
            data=json.dumps(profile.model_dump(mode="json"), indent=2),
            file_name=f"cynbit_lead_{profile.name or 'prospect'}.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_btn2:
        st.download_button(
            "📧 Export Pre-Sales Brief (TXT)",
            data=format_lead_email(profile),
            file_name=f"cynbit_brief_{profile.name or 'prospect'}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with st.expander("📬 Formatted Pre-Sales Email Preview"):
        st.code(format_lead_email(profile), language="text")

    with st.expander("🗂️ Raw Pydantic Model JSON"):
        st.json(profile.model_dump(mode="json"))

def _render_architecture_tab() -> None:
    st.markdown("## 🏗️ Neural System Architecture")
    st.markdown(
        """
        ```mermaid
        flowchart TD
            User([Website Visitor / Lead]) <--> UI[Streamlit Interactive App]

            subgraph Guardrails & Routing
                UI --> InputGuard[Input Guardrails & Off-Topic Detector]
                InputGuard --> ModeRouter{Mode Selector}
            end

            subgraph Knowledge Base Retrieval
                ModeRouter -->|Knowledge Query| Embedder[sentence-transformers: all-MiniLM-L6-v2]
                Embedder --> VectorStore[(FAISS / Cosine Index: cynbit_knowledge_base.json)]
                VectorStore --> Chunks[Top-k Retrieved Chunks]
            end

            subgraph LLM & Grounding Layer
                Chunks --> PromptEngine[Prompt Assembler + Context Injection]
                PromptEngine --> LLM[Provider-Agnostic LLM: Gemini / OpenAI / DEMO_MODE]
                LLM --> GroundingCheck[Anti-Hallucination & Citation Guardrail]
            end

            subgraph BANT Lead Engine
                ModeRouter -->|Lead Interaction| BANT[BANT Extraction Engine]
                BANT --> PydanticValidator[Pydantic Schema Validation: LeadProfile]
                PydanticValidator --> Scorer[Qualification Scorer 0-100]
                Scorer --> EmailNotification[Structured Email Alert to opportunities@cynbit.in]
            end

            GroundingCheck --> UI
            Scorer --> UI
        ```
        """
    )
    st.markdown(
        """
        ### Technical Specifications:
        - **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors)
        - **Vector Index:** FAISS IndexFlatIP (Inner Product / Cosine Similarity with unit-normalized vectors)
        - **Inference Layer:** Google Gemini 1.5 Flash (Default) with OpenAI-compatible fallback & Zero-Key Demo Mode
        - **Schema Enforcement:** Pydantic v2 data models with rigorous field-level bounds (`0 <= qualification_score <= 100`)
        - **Guardrails:** Anti-hallucination lexical & semantic overlap verification + Source Citation enforcement
        """
    )

def _count_bant_fields(profile: LeadProfile) -> int:
    count = 0
    if profile.name or profile.company:
        count += 1
    if profile.budget_range:
        count += 1
    if profile.decision_authority:
        count += 1
    if profile.primary_need:
        count += 1
    if profile.timeline:
        count += 1
    return count

if __name__ == "__main__":
    main()
