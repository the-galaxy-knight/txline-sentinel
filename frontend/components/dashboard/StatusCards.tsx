import type { HealthResponse, ReplayStatus, RuntimeSettings, Signal } from "@/lib/types";
import { compactNumber } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { SourceModeBadge, StatusBadge } from "@/components/ui/Badge";

export function StatusCards({
  health,
  runtime,
  replay,
  signals,
  highConfidence
}: {
  health?: HealthResponse;
  runtime?: RuntimeSettings;
  replay?: ReplayStatus;
  signals?: Signal[];
  highConfidence?: Signal[];
}) {
  const effectiveMode = replay?.status && replay.status !== "idle" ? "replay" : runtime?.ingestion_mode;
  const cards = [
    {
      label: "Agent Status",
      value: health?.status ?? "unknown",
      meta: runtime?.app_env ?? "environment unknown",
      badge: <StatusBadge value={health?.status ?? "unknown"} />
    },
    {
      label: "Backend API",
      value: health?.database ?? runtime?.database ?? "unknown",
      meta: "FastAPI runtime",
      badge: <StatusBadge value={Boolean(health)} />
    },
    {
      label: "Data Source Mode",
      value: (effectiveMode ?? "unknown").toUpperCase(),
      meta: `Configured: ${(runtime?.ingestion_mode ?? "unknown").toUpperCase()}`,
      badge: <SourceModeBadge mode={effectiveMode} />
    },
    {
      label: "Replay Mode",
      value: replay?.status ?? "idle",
      meta: `${replay?.active_run?.events_processed ?? 0}/${replay?.active_run?.events_total ?? 0} events`,
      badge: <StatusBadge value={replay?.status ?? "idle"} />
    },
    {
      label: "Signals Generated",
      value: compactNumber(signals?.length ?? 0),
      meta: "latest fetched signals",
      badge: <StatusBadge value={(signals?.length ?? 0) > 0} />
    },
    {
      label: "High Confidence",
      value: compactNumber(highConfidence?.length ?? 0),
      meta: "confidence >= 80",
      badge: <StatusBadge value={(highConfidence?.length ?? 0) > 0} />
    }
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {cards.map((item) => (
        <Card key={item.label} className="min-h-32">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">{item.label}</p>
              <p className="mt-2 text-2xl font-semibold text-white">{item.value}</p>
              <p className="mt-2 text-sm text-muted">{item.meta}</p>
            </div>
            {item.badge}
          </div>
        </Card>
      ))}
    </div>
  );
}
