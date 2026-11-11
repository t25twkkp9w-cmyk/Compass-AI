from typing import Literal
from pydantic import BaseModel, Field

class Evidence(BaseModel):
    citation_id: str
    source_id: str
    title: str
    text: str
    score: float = 0
    kind: str = "policy"
    metadata: dict = Field(default_factory=dict)

class Claim(BaseModel):
    text: str
    evidence_ids: list[str]

class Guidance(BaseModel):
    route: Literal["answer", "clarify", "abstain", "refuse_bypass"]
    outcome: str
    summary: str
    conditions: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)

class Principal(BaseModel):
    actor_id: str
    name: str
    role: str
    demo: bool = True

class DomainError(ValueError):
    """A reviewable business-rule, validation or authorization failure."""
