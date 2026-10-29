"""
Cynbit IntelliAssist – Main Streamlit Application
AI-powered lead qualification & knowledge assistant for cynbit.in
"""
import os
import sys
import uuid
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
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Cynbit IntelliAssist",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
KB_PATH = str(_ROOT / "data" / "cynbit_knowledge_base.json")
MODES = ["Assistant", "Lead Qualifier", "Knowledge Search"]

WELCOME_MESSAGES = {
    "Assistant": (
        "👋 Hi! I'm **Cynbit IntelliAssist**, your AI guide to everything about "
        "[Cynbit Technologies](https://cynbit.in).\n\n"
        "I can help you with:\n"
        "- 🛠️ **Services** – AI agents, software development, growth & lead generation\n"
        "- 📦 **Products** – BitElevate, TenantEase, Cynbit Studio, Revio\n"
        "- 👥 **Team** – meet the founders and leadership\n"
        "- 💰 **Pricing** – engagement models and how to get started\n"
        "- 📞 **Contact** – reaching the right people\n\n"
        "What would you like to know?"
    ),
    "Lead Qualifier": (
        "👋 Hi! I'm Cynbit's AI sales assistant. I'll ask you a few quick questions to understand "
        "your needs and connect you with the right team member.\n\n"
        "Could you start by telling me your **name** and the **company** you're with?"
    ),
    "Knowledge Search": (
        "🔍 **Knowledge Search Mode**\n\n"
        "Type any query and I'll search Cynbit's knowledge base and show you the "
        "top 3 most relevant results with relevance scores.\n\n"
        "Try: *\"What AI services does Cynbit offer?\"*"
    ),
}

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="📚 Building knowledge base index…")
def load_kb() -> KnowledgeBase:
    """Load and index the knowledge base (cached across sessions)."""
    return KnowledgeBase(data_path=KB_PATH)


# ---------------------------------------------------------------------------
# Session state initialisation
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
# Core RAG pipeline
# ---------------------------------------------------------------------------

def run_rag(query: str, kb: KnowledgeBase, k: int = 3) -> RAGResponse:
    """Run the full RAG pipeline: retrieve → ground → generate."""
    chunks = kb.retrieve(query, k=k)

    if not chunks:
        return RAGResponse(
            answer=(
                "I don't have specific information about that in Cynbit's knowledge base. "
                "Please contact opportunities@cynbit.in for accurate details."
            ),
            sources=[],
            confidence="low",
            grounded=False,
        )

    # Build context from retrieved chunks
    context_parts = []
    for chunk in chunks:
        context_parts.append(f"[Source: {chunk.source}]\nTitle: {chunk.title}\n{chunk.content}")
    context = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "You are Cynbit IntelliAssist, an AI assistant for Cynbit Technologies. "
        "Answer questions based ONLY on the provided context. "
        "Be concise, professional, and helpful. "
        "Always mention contact details (opportunities@cynbit.in) when relevant. "
        "Never fabricate information not present in the context."
    )

    prompt = (
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Answer based only on the context above:"
    )

    raw_answer = generate(prompt, system=system_prompt, temperature=0.1)
    grounded_answer, is_grounded = enforce_grounding(raw_answer, chunks)

    # Determine confidence based on top chunk score
    top_score = chunks[0].score if chunks else 0.0
    if top_score >= 0.6:
        confidence = "high"
    elif top_score >= 0.3:
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
# Lead qualifier pipeline
# ---------------------------------------------------------------------------

def run_lead_qualifier(user_message: str, session: ChatSession) -> str:
    """Process a user message in lead qualifier mode and return assistant response."""
    # Add user turn
    session.turns.append(ConversationTurn(role="user", content=user_message))

    # Extract BANT from full conversation
    profile = extract_bant(session.turns)
    session.lead_profile = profile

    # Generate next question / response
    next_q = get_next_question(profile)
    return next_q


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------

def render_sidebar(kb: KnowledgeBase) -> str:
    """Render sidebar and return selected mode."""
    with st.sidebar:
        st.image(
            "https://via.placeholder.com/200x60/1a1a2e/ffffff?text=Cynbit",
            use_column_width=True,
        )
        st.markdown("## ⚙️ Settings")

        mode = st.selectbox("Mode", MODES, index=MODES.index(st.session_state.mode))

        if mode != st.session_state.mode:
            st.session_state.mode = mode
            reset_conversation()
            st.rerun()

        st.divider()

        # Qualification score
        profile = st.session_state.chat_session.lead_profile
        score = profile.qualification_score
        status = profile.qualification_status

        st.markdown("### 📊 Lead Score")
        st.progress(score / 100)
        col1, col2 = st.columns(2)
        col1.metric("Score", f"{score}/100")
        status_colors = {"hot": "🔴", "warm": "🟡", "cold": "🔵", "unqualified": "⚫"}
        col2.metric("Status", f"{status_colors.get(status, '⚫')} {status.title()}")

        st.divider()

        # BANT completeness
        st.markdown("### 🎯 BANT Progress")
        bant_fields = [
            ("Name/Company", bool(profile.name or profile.company)),
            ("Need", bool(profile.primary_need)),
            ("Budget", bool(profile.budget_range)),
            ("Timeline", bool(profile.timeline)),
            ("Authority", bool(profile.decision_authority)),
        ]
        for field, filled in bant_fields:
            icon = "✅" if filled else "⬜"
            st.markdown(f"{icon} {field}")

        st.divider()

        if st.button("🗑️ Clear Conversation", use_container_width=True):
            reset_conversation()
            st.rerun()

        st.divider()
        st.markdown(
            "**Cynbit Technologies**\n\n"
            "📧 opportunities@cynbit.in\n\n"
            "📞 +91 89479 62667\n\n"
            "🌐 [cynbit.in](https://cynbit.in)"
        )

    return mode


def render_demo_banner() -> None:
    if DEMO_MODE:
        st.info(
            "🔬 **DEMO MODE** – No API key required. "
            "Responses are generated from a curated knowledge base. "
            "Set `LLM_PROVIDER=gemini` and `GEMINI_API_KEY` in `.env` to use live AI.",
            icon="ℹ️",
        )


def render_source_citations(sources: list[RetrievedChunk]) -> None:
    if not sources:
        return
    with st.expander("📚 Sources", expanded=False):
        for i, chunk in enumerate(sources, 1):
            score_pct = int(chunk.score * 100)
            st.markdown(
                f"**{i}. [{chunk.title}]({chunk.source})** "
                f"`[Source: {chunk.source}]` – Relevance: {score_pct}%\n\n"
                f"> {chunk.content[:200]}…"
            )


def render_confidence_badge(confidence: str) -> str:
    badges = {
        "high": "🟢 High confidence",
        "medium": "🟡 Medium confidence",
        "low": "🔴 Low confidence",
    }
    return badges.get(confidence, "")


def render_chat_history(session: ChatSession) -> None:
    for turn in session.turns:
        if turn.role == "user":
            with st.chat_message("user"):
                st.markdown(turn.content)
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(turn.content)


def render_knowledge_search_result(response: RAGResponse) -> None:
    """Render detailed search results for Knowledge Search mode."""
    st.markdown(f"**Answer:** {response.answer}")
    st.markdown(f"*{render_confidence_badge(response.confidence)}*")
    st.divider()
    st.markdown("### 📑 Top Retrieved Chunks")
    for i, chunk in enumerate(response.sources, 1):
        score_pct = int(chunk.score * 100)
        with st.expander(f"#{i} — {chunk.title} (Relevance: {score_pct}%)"):
            st.markdown(f"**Source:** `{chunk.source}`")
            st.markdown(chunk.content)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    init_session()
    kb = load_kb()
    mode = render_sidebar(kb)
    render_demo_banner()

    session: ChatSession = st.session_state.chat_session

    # Page header
    st.title("🤖 Cynbit IntelliAssist")
    st.caption(f"AI-powered knowledge assistant for cynbit.in | Mode: **{mode}**")

    # Show welcome message once per mode
    if mode not in st.session_state.welcome_shown:
        session.turns.append(
            ConversationTurn(role="assistant", content=WELCOME_MESSAGES[mode])
        )
        st.session_state.welcome_shown.add(mode)

    # Tabs
    tab_chat, tab_lead = st.tabs(["💬 Chat", "📋 Lead Summary"])

    with tab_chat:
        # Render conversation history
        render_chat_history(session)

        # Chat input
        if prompt := st.chat_input("Ask me anything about Cynbit…"):
            # Display user message immediately
            with st.chat_message("user"):
                st.markdown(prompt)

            # PII check on user input
            if not check_pii_safety(prompt):
                st.warning("⚠️ Please avoid sharing sensitive personal information in this chat.")

            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Thinking…"):
                    if mode == "Assistant":
                        assistant_response = _handle_assistant_mode(prompt, session, kb)

                    elif mode == "Lead Qualifier":
                        assistant_response = _handle_lead_qualifier_mode(prompt, session)

                    elif mode == "Knowledge Search":
                        assistant_response = _handle_knowledge_search_mode(prompt, session, kb)
                    else:
                        assistant_response = "Unknown mode selected."

                st.markdown(assistant_response)

            # Persist turns
            session.turns.append(ConversationTurn(role="user", content=prompt))
            session.turns.append(ConversationTurn(role="assistant", content=assistant_response))
            st.rerun()

    with tab_lead:
        _render_lead_summary_tab(session)


def _handle_assistant_mode(prompt: str, session: ChatSession, kb: KnowledgeBase) -> str:
    # Off-topic detection
    if detect_off_topic(prompt):
        return get_off_topic_response()

    response = run_rag(prompt, kb)

    # Display sources inline
    if response.sources:
        source_list = ", ".join(f"`{s.source}`" for s in response.sources[:3])
        answer_with_sources = (
            f"{response.answer}\n\n"
            f"*{render_confidence_badge(response.confidence)}* | "
            f"Sources: {source_list}"
        )
        render_source_citations(response.sources)
        return answer_with_sources

    return response.answer


def _handle_lead_qualifier_mode(prompt: str, session: ChatSession) -> str:
    # Add user turn first so extract_bant sees it
    if not session.turns or session.turns[-1].content != prompt:
        session.turns.append(ConversationTurn(role="user", content=prompt))

    profile = extract_bant(session.turns)
    session.lead_profile = profile
    return get_next_question(profile)


def _handle_knowledge_search_mode(prompt: str, session: ChatSession, kb: KnowledgeBase) -> str:
    response = run_rag(prompt, kb, k=3)
    render_knowledge_search_result(response)
    return ""  # Content rendered above via st components


def _render_lead_summary_tab(session: ChatSession) -> None:
    profile = session.lead_profile
    st.markdown("## 📋 Lead Qualification Summary")

    if profile.qualification_status == "unqualified" and profile.qualification_score == 0:
        st.info("Start a conversation in **Lead Qualifier** mode to see the live lead profile here.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Qualification Score", f"{profile.qualification_score}/100")
    col2.metric("Status", profile.qualification_status.title())
    col3.metric("BANT Fields", f"{_count_bant_fields(profile)}/5")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 👤 Identity")
        st.markdown(f"**Name:** {profile.name or '_Not provided_'}")
        st.markdown(f"**Company:** {profile.company or '_Not provided_'}")

    with col_b:
        st.markdown("### 🎯 Services of Interest")
        if profile.service_interest:
            for svc in profile.service_interest:
                st.markdown(f"- {svc}")
        else:
            st.markdown("_Not specified_")

    st.markdown("### 🔍 BANT Details")
    bant_data = {
        "Budget": profile.budget_range or "_Not disclosed_",
        "Authority": profile.decision_authority or "_Not identified_",
        "Need": profile.primary_need or "_Not specified_",
        "Timeline": profile.timeline or "_Not specified_",
    }
    for label, value in bant_data.items():
        st.markdown(f"**{label}:** {value}")

    st.divider()
    st.markdown(f"**Next Action:** {profile.next_action}")

    st.divider()
    st.markdown("### 📧 Email Summary")
    st.code(format_lead_email(profile), language="")

    st.divider()
    st.markdown("### 🗂️ Raw JSON Profile")
    st.json(profile.model_dump(mode="json"))


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

