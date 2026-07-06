from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    symbol: str
    file_path: str
    line_number: int | None = None
    source_type: str | None = None
    code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
