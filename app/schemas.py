"""The JSON contract. Every module reads/writes these models.

Change this file only with both teammates agreeing — it is the interface
between the analyzers (deterministic), the LLM layer, and the API.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

SourceType = Literal["code", "resume"]


class Finding(BaseModel):
    """One measurable problem found by an analyzer (no LLM involved)."""
    id: str = Field(..., examples=["f1"])
    location: str = Field(..., examples=["utils.py:42-88", "bullet 3"])
    metric: str = Field(..., examples=["nesting_depth", "weak_verb"])
    value: float | int | str
    threshold: Optional[float | int | str] = None
    severity: float = Field(..., ge=0, le=1, description="0 = cosmetic, 1 = crime scene")
    snippet: str = Field("", description="Original code/text the finding refers to")
    detail: str = ""


class AnalysisResult(BaseModel):
    source_type: SourceType
    findings: list[Finding]
    summary: dict = Field(default_factory=dict)


class AnalyzeCodeRequest(BaseModel):
    code: Optional[str] = Field(None, description="Pasted Python source")
    repo_url: Optional[str] = Field(None, examples=["https://github.com/owner/repo"])
    max_findings: int = Field(8, ge=1, le=25)

    @model_validator(mode="after")
    def one_source(self):
        if not (self.code or self.repo_url):
            raise ValueError("Provide either 'code' or 'repo_url'.")
        return self


class RoastRequest(BaseModel):
    analysis: AnalysisResult
    persona: str = Field("gordon_ramsay", examples=["gordon_ramsay"])


class RoastLine(BaseModel):
    finding_id: str
    text: str


class RoastResponse(BaseModel):
    persona: str
    opener: str = ""
    roast: list[RoastLine]
    mode: Literal["live", "demo"]


class MercyRequest(BaseModel):
    analysis: AnalysisResult
    finding_ids: Optional[list[str]] = Field(None, description="Subset to fix; default all")


class MercyItem(BaseModel):
    finding_id: str
    original: str
    revised: str
    explanation: str = ""
    valid: bool = Field(..., description="Code: passes ast.parse. Resume: passes bullet rules.")
    attempts: int = 1
    # Behavior-equivalence check (code only). None = not run or not testable.
    equivalent: Optional[bool] = Field(None, description="Same outputs/exceptions as the original")
    cases_checked: int = 0
    mismatches: list[dict] = Field(default_factory=list,
                                   description="Inputs where original and rewrite differ")
    equivalence_note: str = ""


class MercyResponse(BaseModel):
    items: list[MercyItem]
    mode: Literal["live", "demo"]


class Persona(BaseModel):
    id: str
    name: str
    description: str
