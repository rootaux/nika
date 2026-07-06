from typing import Any

from pydantic import BaseModel, Field


class Sink(BaseModel):
    rule_id: str | None = None
    file_path: str
    line_number: int
    line_number_end: int | None = None
    code: str
    metadata: dict[str, Any] = Field(default_factory=dict)
