import type { Signal } from "@/lib/types";
import {
  formatConfidence,
  formatDateTime,
  formatProbability,
  formatProbabilityDelta,
  formatSignalType
} from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { SourceModeBadge, StatusBadge } from "@/components/ui/Badge";
import { SignalEvaluationBadges } from "./SignalEvaluationBadges";

export function SignalDetail({ signal }: { signal: Signal }) {
  const breakdown = [
    ["Magnitude", signal.magnitude_score],
    ["Velocity", signal.velocity_score],
    ["Volatility", signal.volatility_score],
    ["Freshness", signal.freshness_score],
    ["Context", signal.context_score],
    ["Bookmaker agreement", signal.trade_relevance_score]
  ];

  return (
    <div className="space-y-5">
      <Card title={formatSignalType(signal.signal_type)} eyebrow={`Signal #${signal.id}`} action={<SourceModeBadge mode={signal.source_mode} />}>
        <div className="flex flex-wrap gap-2">
          <StatusBadge value={signal.status ?? "new"} />
          <StatusBadge value={signal.explanation_source ?? "template"} />
        </div>
        <div className="mt-5 grid gap-4 md:grid-cols-4">
          <Metric label="Fixture" value={signal.fixture_id ?? "unknown"} />
          <Metric label="Outcome" value={signal.outcome_name ?? "unknown"} />
          <Metric label="Probability" value={`${formatProbability(signal.probability_before)} → ${formatProbability(signal.probability_after)}`} />
          <Metric label="Confidence" value={formatConfidence(signal.confidence_score)} />
          <Metric label="Delta" value={formatProbabilityDelta(signal.delta_probability)} />
          <Metric label="Direction" value={signal.direction ?? "flat"} />
          <Metric label="Window" value={`${signal.window_seconds ?? 0}s`} />
          <Metric label="Created" value={formatDateTime(signal.created_at)} />
        </div>
      </Card>

      <Card title="Explanation" eyebrow="Agent rationale">
        <p className="whitespace-pre-wrap text-sm leading-6 text-slate-200">{signal.explanation ?? "No explanation available."}</p>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Confidence Breakdown" eyebrow="Scoring inputs">
          <div className="space-y-3">
            {breakdown.map(([label, value]) => (
              <div key={label as string}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted">{label}</span>
                  <span className="text-white">{value === null || value === undefined ? "n/a" : Number(value).toFixed(2)}</span>
                </div>
                <div className="h-2 rounded bg-slate-800">
                  <div className="h-2 rounded bg-emerald-400" style={{ width: `${Math.min(Number(value ?? 0) * 100, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Predictiveness Tracking" eyebrow="5/10/15 minute horizons">
          <SignalEvaluationBadges evaluations={signal.evaluations} />
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr>
                  <th className="py-2">Horizon</th>
                  <th>Result</th>
                  <th>Delta</th>
                  <th>Evaluated</th>
                </tr>
              </thead>
              <tbody>
                {(signal.evaluations ?? []).map((evaluation) => (
                  <tr key={evaluation.id} className="border-t border-slate-800">
                    <td className="py-2">{evaluation.horizon_minutes}m</td>
                    <td>{evaluation.result}</td>
                    <td>{formatProbabilityDelta(evaluation.delta_after_signal)}</td>
                    <td>{formatDateTime(evaluation.evaluated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <Card title="Raw Context" eyebrow="Technical details">
        <pre className="max-h-96 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-300">
          {JSON.stringify(
            {
              score_context: signal.score_context,
              raw_features: signal.raw_features,
              market_key: signal.market_key
            },
            null,
            2
          )}
        </pre>
      </Card>
    </div>
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
