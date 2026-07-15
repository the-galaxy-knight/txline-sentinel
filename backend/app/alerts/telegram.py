from __future__ import annotations

import httpx

from app.config import Settings
from app.db import Signal
from app.explanation.templates import SIGNAL_LABELS


class TelegramClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_signal(self, signal: Signal) -> None:
        if not self.settings.telegram_bot_token or not self.settings.telegram_chat_id:
            raise RuntimeError("Telegram bot token or chat id is not configured.")
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.settings.telegram_chat_id,
                    "text": format_signal_message(signal),
                    "disable_web_page_preview": True,
                },
            )
            response.raise_for_status()


def format_signal_message(signal: Signal) -> str:
    label = SIGNAL_LABELS.get(signal.signal_type, signal.signal_type.replace("_", " ").title())
    probability = (
        f"{signal.probability_before * 100:.1f}% -> {signal.probability_after * 100:.1f}%"
    )
    confidence = f"{signal.confidence_score:.0f}/100"
    return (
        "TxLINE Sentinel Signal\n\n"
        f"Fixture: {signal.fixture_id}\n"
        f"Signal: {label.title()}\n"
        f"Market: {signal.market_key}\n"
        f"Outcome: {signal.outcome_name}\n"
        f"Probability: {probability}\n"
        f"Confidence: {confidence}\n\n"
        f"{signal.explanation or ''}\n\n"
        "Status: follow-through pending at 5/10/15 minutes."
    )
