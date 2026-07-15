from __future__ import annotations

from collections.abc import AsyncIterator, Iterable

from pydantic import BaseModel


class SseEvent(BaseModel):
    id: str | None = None
    event: str | None = None
    data: str


def _parse_sse_lines(lines: Iterable[str]) -> list[SseEvent]:
    events: list[SseEvent] = []
    event_id: str | None = None
    event_type: str | None = None
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event_id, event_type, data_lines
        if event_id is not None or event_type is not None or data_lines:
            events.append(SseEvent(id=event_id, event=event_type, data="\n".join(data_lines)))
        event_id = None
        event_type = None
        data_lines = []

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            flush()
            continue
        if line.startswith(":"):
            continue

        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]

        if field == "id":
            event_id = value
        elif field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)

    flush()
    return events


def parse_sse_text(text: str) -> list[SseEvent]:
    return _parse_sse_lines(text.splitlines())


async def iter_sse_events(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    event_id: str | None = None
    event_type: str | None = None
    data_lines: list[str] = []

    async for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line:
            if event_id is not None or event_type is not None or data_lines:
                yield SseEvent(id=event_id, event=event_type, data="\n".join(data_lines))
            event_id = None
            event_type = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue

        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]

        if field == "id":
            event_id = value
        elif field == "event":
            event_type = value
        elif field == "data":
            data_lines.append(value)

    if event_id is not None or event_type is not None or data_lines:
        yield SseEvent(id=event_id, event=event_type, data="\n".join(data_lines))
