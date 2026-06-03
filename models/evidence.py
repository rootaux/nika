from pydantic import BaseModel, Field

from .sink import Sink
from .source import Source
from .trace import Trace


class EvidenceBundle(BaseModel):
    sources: list[Source] = Field(default_factory=list)
    sinks: list[Sink] = Field(default_factory=list)
    traces: list[Trace] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
    raw_payload: dict = Field(default_factory=dict)
    parsed_payload: list[dict] = Field(default_factory=list)
