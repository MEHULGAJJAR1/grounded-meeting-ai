"""Strict Pydantic contracts used by OpenAI Structured Outputs and local extraction.

Extraction confidence is a proposal, not the final score. A separate verifier owns
final evidence locations, metadata fallbacks, support verdicts and confidence.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(StrictModel):
    quote: str = Field(min_length=1, max_length=5000)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=4000)
    evidence: list[Evidence] = Field(min_length=1, max_length=5)
    confidence: float = Field(ge=0, le=1)


class ActionClaim(Claim):
    owner: str = Field(max_length=120)
    owner_evidence: str = Field(max_length=5000)
    due_date: str = Field(max_length=150)
    due_date_evidence: str = Field(max_length=5000)
    priority: Literal["Low", "Medium", "High", "Critical"]
    priority_evidence: str = Field(max_length=5000)
    status: Literal["Pending", "In Progress", "Completed", "Blocked", "Cancelled"]
    status_evidence: str = Field(max_length=5000)
    dependencies: list[Claim] = Field(max_length=20)


class DecisionClaim(Claim):
    decision_type: Literal["Confirmed", "Tentative", "Rejected"]


class RiskClaim(Claim):
    category: Literal[
        "Blocker", "Dependency", "Delivery", "Technical", "Resource", "Unresolved issue"
    ]
    severity: Literal["Unknown", "Low", "Medium", "High", "Critical"]
    severity_evidence: str = Field(max_length=5000)


class Sentiment(StrictModel):
    label: Literal["Positive", "Neutral", "Concerned", "Mixed", "Not enough evidence"]
    description: str
    evidence: list[Evidence] = Field(max_length=5)


class ExtractionOutput(StrictModel):
    three_line_summary: list[Claim] = Field(max_length=3)
    executive_summary: list[Claim] = Field(max_length=8)
    detailed_summary: list[Claim] = Field(max_length=30)
    bullet_summary: list[Claim] = Field(max_length=20)
    key_points: list[Claim] = Field(max_length=30)
    decisions: list[DecisionClaim] = Field(max_length=50)
    action_items: list[ActionClaim] = Field(max_length=80)
    risks: list[RiskClaim] = Field(max_length=50)
    questions: list[Claim] = Field(max_length=40)
    follow_ups: list[Claim] = Field(max_length=30)
    commitments: list[Claim] = Field(max_length=30)
    dependencies: list[Claim] = Field(max_length=30)
    projects: list[Claim] = Field(max_length=30)
    people: list[Claim] = Field(max_length=80)
    important_dates: list[Claim] = Field(max_length=40)
    topics: list[Claim] = Field(max_length=30)
    sentiment: Sentiment


class Verification(StrictModel):
    claim_id: str
    verdict: Literal["supported", "unsupported", "uncertain"]
    reason: str
    score: float = Field(ge=0, le=1)


class VerificationBatch(StrictModel):
    checks: list[Verification]


class AnswerClaim(StrictModel):
    text: str
    source_ids: list[str] = Field(min_length=1, max_length=5)
    evidence_quotes: list[str] = Field(min_length=1, max_length=5)


class RAGAnswer(StrictModel):
    claims: list[AnswerClaim] = Field(max_length=12)
    insufficient_evidence: bool
    explanation: str


class ValidatedEvidence(Evidence):
    filename: str | None = None
    page: int | None = Field(default=None, ge=1)
    section: int | None = Field(default=None, ge=1)


class ValidatedClaim(Claim):
    evidence: list[ValidatedEvidence] = Field(min_length=1, max_length=5)
    grounding_status: Literal["verified", "review"]


class ValidatedAction(ActionClaim):
    evidence: list[ValidatedEvidence] = Field(min_length=1, max_length=5)
    dependencies: list[ValidatedClaim]
    grounding_status: Literal["verified", "review"]
    priority_provenance: Literal["transcript", "application_default"]
    status_provenance: Literal["transcript", "application_default"]


class ValidatedDecision(DecisionClaim):
    evidence: list[ValidatedEvidence] = Field(min_length=1, max_length=5)
    grounding_status: Literal["verified", "review"]


class ValidatedRisk(RiskClaim):
    evidence: list[ValidatedEvidence] = Field(min_length=1, max_length=5)
    grounding_status: Literal["verified", "review"]


class ValidatedSentiment(Sentiment):
    evidence: list[ValidatedEvidence]


class FinalIntelligence(StrictModel):
    """A second validation barrier after verification, before atomic persistence."""

    three_line_summary: list[ValidatedClaim]
    executive_summary: list[ValidatedClaim]
    detailed_summary: list[ValidatedClaim]
    bullet_summary: list[ValidatedClaim]
    key_points: list[ValidatedClaim]
    decisions: list[ValidatedDecision]
    action_items: list[ValidatedAction]
    risks: list[ValidatedRisk]
    questions: list[ValidatedClaim]
    follow_ups: list[ValidatedClaim]
    commitments: list[ValidatedClaim]
    dependencies: list[ValidatedClaim]
    projects: list[ValidatedClaim]
    people: list[ValidatedClaim]
    important_dates: list[ValidatedClaim]
    topics: list[ValidatedClaim]
    sentiment: ValidatedSentiment
