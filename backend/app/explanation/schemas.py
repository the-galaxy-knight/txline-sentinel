from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


class ExplanationOutput(BaseModel):
    title: str
    summary: str
    why_it_matters: str
    caveat: str
    confidence_label: Literal["low", "medium", "high"]


@dataclass(frozen=True)
class GeneratedExplanation:
    text: str
    source: Literal["template", "llm", "fallback"]
