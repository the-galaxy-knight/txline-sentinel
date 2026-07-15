import type { MatchState } from "@/lib/types";
import { formatProbability, formatProbabilityDelta } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";

export function MatchStateCard({ state }: { state?: MatchState }) {
  const score = state?.score;
  return (
    <Card title="Match State" eyebrow={state?.fixture_id ?? "fixture"}>
      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Score" value={score ? `${score.participant_1_score ?? "-"}-${score.participant_2_score ?? "-"}` : "unknown"} />
        <Metric label="Game state" value={score?.game_state ?? "unknown"} />
        <Metric label="Clock" value={score?.clock_seconds ? `${score.clock_seconds}s` : "unknown"} />
        <Metric label="Last action" value={score?.last_action ?? "none"} />
      </div>
      <div className="mt-5 flex flex-wrap gap-2">
        {(state?.markets ?? []).slice(0, 6).map((market) => (
          <div key={market.market_key} className="rounded-md border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm">
            <p className="font-semibold text-white">{market.outcome_name ?? "Outcome"}</p>
            <p className="text-muted">
              {formatProbability(market.p_now)} · {formatProbabilityDelta(market.delta_300s)}
            </p>
          </div>
        ))}
        {(state?.latest_signals?.length ?? 0) > 0 && <StatusBadge value={`${state?.latest_signals?.length} signals`} />}
      </div>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
