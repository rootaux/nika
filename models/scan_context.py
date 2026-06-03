from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    path: str
    language: str = "java"
    output: str = "report.html"
    source_branch: str | None = None
    target_branch: str | None = None
    enabled_vulnerabilities: list[str] = Field(default_factory=list)


class ScanContext(ScanRequest):
    baseline_commit: str | None = None
    review_llm_enabled: bool = False
    engine_selection: dict[str, str] = Field(default_factory=dict)
