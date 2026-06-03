from pydantic import BaseModel, Field


class Source(BaseModel):
    symbol: str
    file_path: str
    line_number: int | None = None
    source_type: str | None = None
    code: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
