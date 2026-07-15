import type { DashboardStreamEvent } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/Badge";

export function AgentTimeline({
  events,
  streamState
}: {
  events: DashboardStreamEvent[];
  streamState: "connected" | "disconnected" | "error";
}) {
  return (
    <Card
      title="Agent Timeline"
      eyebrow="SSE stream"
      action={<StatusBadge value={streamState === "connected" ? "running" : "disconnected"} />}
    >
      {events.length === 0 ? (
        <EmptyState message="No live dashboard events yet. Start a replay to watch the agent pipeline move." />
      ) : (
        <div className="space-y-3">
          {events.slice(0, 12).map((event, index) => (
            <div key={`${event.created_at}-${event.type}-${index}`} className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-white">{event.type ?? "event"}</p>
                <p className="text-xs text-muted">{formatDateTime(event.created_at)}</p>
              </div>
              <pre className="mt-2 max-h-20 overflow-hidden text-xs text-slate-400">
                {JSON.stringify(event.payload ?? {}, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}
