"""
Pydantic schemas for Cynbit IntelliAssist structured outputs.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class RetrievedChunk(BaseModel):
    """A single retrieved document chunk from the knowledge base."""
    chunk_id: str
    source: str
    title: str
    content: str
    score: float


class RAGResponse(BaseModel):
    """Structured response from the RAG pipeline."""
    answer: str
    sources: list[RetrievedChunk]
    confidence: Literal["high", "medium", "low"]
    grounded: bool  # True if answer is supported by retrieved chunks


class LeadProfile(BaseModel):
    """BANT-based lead qualification profile."""
    name: Optional[str] = None
    company: Optional[str] = None
    budget_range: Optional[str] = None        # BANT: Budget
    decision_authority: Optional[str] = None   # BANT: Authority
    primary_need: Optional[str] = None         # BANT: Need
    timeline: Optional[str] = None             # BANT: Timeline
    service_interest: Optional[list[str]] = Field(default_factory=list)
    qualification_score: int = Field(ge=0, le=100)
    qualification_status: Literal["hot", "warm", "cold", "unqualified"]
    next_action: str
    collected_at: datetime = Field(default_factory=datetime.utcnow)


class ConversationTurn(BaseModel):
    """A single turn in a conversation."""
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(BaseModel):
    """A full chat session with conversation history and lead profile."""
    session_id: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    lead_profile: LeadProfile = Field(
        default_factory=lambda: LeadProfile(
            qualification_score=0,
            qualification_status="unqualified",
            next_action="gather_info"
        )
    )

