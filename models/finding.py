from pydantic import BaseModel, Field

from .trace import Trace


class Finding(BaseModel):
    vulnerability_id: str
    sink: str
    file_path: str | None = None
    line_number: int | None = None
    line_number_end: int | None = None
    status: str = "VULNERABLE"
    explanation: str | None = None
    remediation: str | None = None
    code_fix: str | None = None
    trace: Trace | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
