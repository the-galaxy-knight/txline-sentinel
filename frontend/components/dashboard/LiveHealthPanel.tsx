import type { LiveStreamStatus, RuntimeSettings } from "@/lib/types";
import { compactNumber, formatDateTime } from "@/lib/format";
import { SourceModeBadge, StatusBadge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";

export function LiveHealthPanel({ runtime }: { runtime?: RuntimeSettings }) {
  const streams = Object.entries(runtime?.live_streams ?? {});
  const totalEvents = streams.reduce(
    (total, [, stream]) => total + (stream.events_received ?? 0),
    0
  );

  return (
    <Card
      title="TxLINE Live Health"
      eyebrow="Live proof"
      action={<SourceModeBadge mode={runtime?.ingestion_mode} />}
    >
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <SummaryMetric label="TxLINE" value={runtime?.txline_configured ? "Configured" : "Missing"} />
        <SummaryMetric label="Streams" value={compactNumber(streams.length)} />
        <SummaryMetric label="Events" value={compactNumber(totalEvents)} />
      </div>

      {streams.length === 0 ? (
        <EmptyState message="No live stream status reported yet. Start the backend with INGESTION_MODE=live to initialize stream monitoring." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {streams.map(([key, stream]) => (
            <StreamCard key={key} name={key} stream={stream} />
          ))}
        </div>
      )}
    </Card>
  );
}

function StreamCard({ name, stream }: { name: string; stream: LiveStreamStatus }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/45 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">{name} stream</p>
          <p className="mt-1 text-sm font-semibold text-white">
            {(stream.name ?? name).toUpperCase()}
          </p>
        </div>
        <StatusBadge value={stream.state ?? "unknown"} />
      </div>

      <dl className="mt-4 grid gap-3">
        <Row label="Events received" value={compactNumber(stream.events_received ?? 0)} />
        <Row label="Last event timestamp" value={formatDateTime(stream.last_event_at)} />
        <Row label="Last event ID" value={stream.last_event_id ?? "n/a"} mono />
        <Row label="Reconnect attempts" value={compactNumber(stream.reconnect_attempts ?? 0)} />
      </dl>

      {stream.last_error && (
        <p className="mt-4 rounded-md border border-amber-400/25 bg-amber-400/10 p-3 text-xs leading-5 text-amber-100">
          {stream.last_error}
        </p>
      )}
    </div>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950/45 p-3">
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid gap-1">
      <dt className="text-xs text-muted">{label}</dt>
      <dd
        className={`text-sm text-slate-100 ${mono ? "break-all font-mono text-xs leading-5" : ""}`}
      >
        {value}
      </dd>
    </div>
  );
}
