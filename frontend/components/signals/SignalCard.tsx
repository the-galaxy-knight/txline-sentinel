import Link from "next/link";
import type { Signal } from "@/lib/types";
import {
  formatConfidence,
  formatDateTime,
  formatProbability,
  formatProbabilityDelta,
  formatSignalType
} from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { Badge, SourceModeBadge, StatusBadge } from "@/components/ui/Badge";
import { SignalEvaluationBadges } from "./SignalEvaluationBadges";

export function SignalCard({ signal }: { signal: Signal }) {
  const highConfidence = (signal.confidence_score ?? 0) >= 80;
  return (
    <Card
      className="h-full"
      title={formatSignalType(signal.signal_type)}
      eyebrow={signal.fixture_id}
      action={<SourceModeBadge mode={signal.source_mode} />}
    >
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge value={signal.status ?? "new"} />
        {highConfidence && <Badge tone="green">High confidence</Badge>}
        <Badge tone={signal.direction === "down" ? "red" : "blue"}>{signal.direction ?? "flat"}</Badge>
      </div>
      <p className="mt-4 text-lg font-semibold text-white">{signal.outcome_name ?? "Unknown outcome"}</p>
      <div className="mt-3 grid gap-3 text-sm md:grid-cols-3">
        <div>
          <p className="text-muted">Probability</p>
          <p className="mt-1 text-white">
            {formatProbability(signal.probability_before)} → {formatProbability(signal.probability_after)}
          </p>
        </div>
        <div>
          <p className="text-muted">Delta</p>
          <p className="mt-1 text-white">{formatProbabilityDelta(signal.delta_probability)}</p>
        </div>
        <div>
          <p className="text-muted">Confidence</p>
          <p className="mt-1 text-white">{formatConfidence(signal.confidence_score)}</p>
        </div>
      </div>
      <p className="mt-4 line-clamp-3 text-sm text-slate-300">
        {signal.explanation ?? "No explanation generated yet."}
      </p>
      <div className="mt-4">
        <SignalEvaluationBadges evaluations={signal.evaluations} />
      </div>
      <div className="mt-4 flex items-center justify-between gap-3 text-xs text-muted">
        <span>{formatDateTime(signal.created_at)}</span>
        <Link href={`/signals/${signal.id}`} className="font-semibold text-emerald-300 hover:text-emerald-200">
          Inspect signal
        </Link>
      </div>
    </Card>
  );
}
