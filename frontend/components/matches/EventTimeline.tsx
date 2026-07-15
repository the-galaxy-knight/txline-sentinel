import type { OddsEvent, ScoreEvent } from "@/lib/types";
import { formatDateTime, formatProbability } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { SourceModeBadge } from "@/components/ui/Badge";

export function EventTimeline({
  oddsEvents = [],
  scoreEvents = []
}: {
  oddsEvents?: OddsEvent[];
  scoreEvents?: ScoreEvent[];
}) {
  const rows = [
    ...oddsEvents.map((event) => ({
      id: `odds-${event.id}`,
      type: "odds",
      ts: event.tx_ts ?? event.received_at,
      source: event.source_mode,
      title: `${event.outcome_name ?? "Outcome"} ${formatProbability(event.implied_probability)}`,
      detail: event.bookmaker ?? event.odds_type ?? "odds event"
    })),
    ...scoreEvents.map((event) => ({
      id: `score-${event.id}`,
      type: "score",
      ts: event.tx_ts ?? event.received_at,
      source: event.source_mode,
      title: event.action ?? "Score event",
      detail: `${event.participant_1_score ?? "-"}-${event.participant_2_score ?? "-"}`
    }))
  ].sort((a, b) => new Date(b.ts ?? 0).getTime() - new Date(a.ts ?? 0).getTime());

  return (
    <Card title="Event Timeline" eyebrow="Odds and score events">
      <div className="space-y-3">
        {rows.slice(0, 30).map((row) => (
          <div key={row.id} className="flex items-start justify-between gap-3 rounded-md border border-slate-800 bg-slate-950/60 p-3">
            <div>
              <p className="text-sm font-semibold text-white">{row.title}</p>
              <p className="mt-1 text-xs text-muted">{row.detail} · {formatDateTime(row.ts)}</p>
            </div>
            <SourceModeBadge mode={row.source} />
          </div>
        ))}
      </div>
    </Card>
  );
}
