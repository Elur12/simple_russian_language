from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["green", "orange", "red"]

SEVERITY_WEIGHT: dict[str, int] = {"green": 1, "orange": 2, "red": 3}


class ViolationDetail(BaseModel):
    rule_id: str
    rule_name: str = ""
    severity: Severity
    problematic_text: str = ""
    comment: str = ""
    suggested_rewrite: str = ""


class SentenceFinding(BaseModel):
    sentence_index: int
    severity: Severity
    violations: list[ViolationDetail] = Field(default_factory=list)
    comment: str = ""
    suggested_rewrite: str = ""


class ParagraphFinding(BaseModel):
    unit_index: int
    unit_type: Literal["paragraph"] = "paragraph"
    source_text: str
    severity: Severity
    violations: list[ViolationDetail] = Field(default_factory=list)
    overall_comment: str = ""
    paragraph_rewrite: str = ""
    sentence_findings: list[SentenceFinding] = Field(default_factory=list)


class AnalysisSummary(BaseModel):
    green: int = 0
    orange: int = 0
    red: int = 0
    overall: Severity = "green"


class AnalysisResponse(BaseModel):
    summary: AnalysisSummary
    items: list[ParagraphFinding] = Field(default_factory=list)
