"""Optional alert dispatch orchestration."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.alerts.telegram import TelegramClient
from app.config import Settings, get_settings
from app.db import SessionLocal, Signal, TelegramAlert

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Send eligible high-confidence signals to configured alert channels."""

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.telegram = TelegramClient(self.settings)

    async def dispatch_signal(self, signal_id: int) -> None:
        """Dispatch a signal alert without allowing alert failures to break ingestion."""

        if not self.settings.telegram_configured:
            return

        with self.session_factory() as db:
            signal = db.get(Signal, signal_id)
            if signal is None:
                return
            if signal.confidence_score < self.settings.telegram_min_confidence:
                return

            alert = TelegramAlert(
                signal_id=signal.id,
                chat_id=self.settings.telegram_chat_id,
                status="pending",
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

        try:
            await self.telegram.send_signal(signal)
        except Exception as exc:
            logger.exception("Telegram alert failed for signal %s.", signal_id)
            with self.session_factory() as db:
                stored = db.get(TelegramAlert, alert.id)
                if stored:
                    stored.status = "failed"
                    stored.error_message = str(exc)
                    db.commit()
            return

        with self.session_factory() as db:
            stored = db.get(TelegramAlert, alert.id)
            signal = db.get(Signal, signal_id)
            if stored:
                stored.status = "sent"
                stored.sent_at = datetime.now(UTC)
            if signal:
                signal.status = "alerted"
            db.commit()
