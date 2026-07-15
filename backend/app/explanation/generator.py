"""Generate safe signal explanations with deterministic fallback.

The signal engine supplies structured facts. The optional LLM can only rewrite
those facts into concise prose; if configuration, validation, import, or timeout
fails, the template explanation is used instead.
"""

from __future__ import annotations

import asyncio
import json
import logging

from app.config import Settings, get_settings
from app.explanation.prompts import SYSTEM_PROMPT, user_prompt
from app.explanation.schemas import ExplanationOutput, GeneratedExplanation
from app.explanation.templates import template_explanation
from app.signals.models import ScoredSignal

logger = logging.getLogger(__name__)


class ExplanationGenerator:
    """Create an explanation for a scored signal."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, scored: ScoredSignal) -> GeneratedExplanation:
        """Return an LLM explanation when safe and available, otherwise template text."""

        template = template_explanation(scored)
        if not self.settings.llm_configured:
            return GeneratedExplanation(text=template, source="template")

        try:
            output = await asyncio.wait_for(
                self._generate_with_llm(scored),
                timeout=self.settings.llm_timeout_seconds,
            )
            text = "\n".join(
                [
                    output.title,
                    output.summary,
                    output.why_it_matters,
                    output.caveat,
                ]
            )
            return GeneratedExplanation(text=text, source="llm")
        except Exception as exc:
            logger.warning("LLM explanation failed; using template fallback: %s", exc)
            return GeneratedExplanation(text=template, source="fallback")

    async def _generate_with_llm(self, scored: ScoredSignal) -> ExplanationOutput:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed.") from exc

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        response = await client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt(_facts(scored))},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return ExplanationOutput.model_validate(json.loads(content))


def _facts(scored: ScoredSignal) -> dict:
    candidate = scored.candidate
    score_context = candidate.score_context.to_dict() if candidate.score_context else {}
    return {
        "signal_type": candidate.signal_type,
        "outcome_name": candidate.outcome_name,
        "direction": candidate.direction,
        "probability_before": candidate.probability_before,
        "probability_after": candidate.probability_after,
        "delta_probability": candidate.delta_probability,
        "window_seconds": candidate.window_seconds,
        "confidence_score": scored.confidence_score,
        "score_context": score_context,
        "allowed_language": "may indicate; follow-through pending; no bet recommendation",
    }
