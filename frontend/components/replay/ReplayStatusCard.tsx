import type { ReplayStatus } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { StatusBadge, SourceModeBadge } from "@/components/ui/Badge";

export function ReplayStatusCard({ replay }: { replay?: ReplayStatus }) {
  const run = replay?.active_run;
  return (
    <Card title="Replay Status" eyebrow="Pipeline state" action={<SourceModeBadge mode={run ? "replay" : "disabled"} />}>
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <div>
          <p className="text-muted">Status</p>
          <div className="mt-1"><StatusBadge value={replay?.status ?? "idle"} /></div>
        </div>
        <div>
          <p className="text-muted">Scenario</p>
          <p className="mt-1 text-white">{run?.scenario_name ?? "none"}</p>
        </div>
        <div>
          <p className="text-muted">Speed</p>
          <p className="mt-1 text-white">{run?.speed_multiplier ? `${run.speed_multiplier}x` : "n/a"}</p>
        </div>
        <div>
          <p className="text-muted">Events processed</p>
          <p className="mt-1 text-white">{run?.events_processed ?? 0}/{run?.events_total ?? 0}</p>
        </div>
        <div>
          <p className="text-muted">Cursor</p>
          <p className="mt-1 text-white">{run?.cursor_position ?? 0}</p>
        </div>
        <div>
          <p className="text-muted">Started</p>
          <p className="mt-1 text-white">{formatDateTime(run?.started_at)}</p>
        </div>
      </div>
    </Card>
  );
}
