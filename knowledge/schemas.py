from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Confidence = Literal["high", "medium", "low"]


class Citation(BaseModel):
    document_id: str = Field(description="Exact ID of a document returned by retrieval")
    title: str
    source: str
    section: str | None = None
    url: str | None = None


class QAResponse(BaseModel):
    answer: str
    confidence: Confidence
    citations: list[Citation] = Field(default_factory=list)
    insufficient_context: bool = False
    missing_information: list[str] = Field(default_factory=list)
    recommended_action: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=2)
    thread_id: str | None = Field(default=None, max_length=200)
    product: str | None = Field(default=None, max_length=100)
    document_type: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        return " ".join(value.strip().split())


class RetrievalSummary(BaseModel):
    documents_considered: int
    validated_citations: int
    query_understanding: dict[str, Any] | None = None


class QueryResponse(QAResponse):
    retrieval: RetrievalSummary


class AskResponse(QueryResponse):
    """Dashboard ask payload — includes the conversation thread id."""

    thread_id: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    qdrant: str


class SourceArtifact(BaseModel):
    document_id: str
    title: str
    source: str
    section: str | None = None
    url: str | None = None
    product: str | None = None
    version: str | None = None
    tenant_id: str
    access_level: str
    updated_at: str | None = None
    score: float
    content: str


class IngestStats(BaseModel):
    files_seen: int
    documents_indexed: int
    files_failed: int


class RemediationRequest(BaseModel):
    issue: str = Field(min_length=2, max_length=4000)
    thread_id: str | None = Field(default=None, max_length=200)

    @field_validator("issue")
    @classmethod
    def clean_issue(cls, value: str) -> str:
        return " ".join(value.strip().split())


class RemediationResumeRequest(BaseModel):
    thread_id: str = Field(min_length=2, max_length=200)
    decision: Literal["approve", "reject"] = "approve"
    message: str | None = Field(default=None, max_length=1000)
