import type { SignalEvaluation } from "@/lib/types";
import { formatEvaluationResult } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";

function toneFor(result?: string) {
  if (result === "confirmed") return "green";
  if (result === "failed") return "red";
  if (result === "neutral") return "blue";
  return "amber";
}

export function SignalEvaluationBadges({ evaluations = [] }: { evaluations?: SignalEvaluation[] }) {
  const horizons = [5, 10, 15];
  return (
    <div className="flex flex-wrap gap-2">
      {horizons.map((minutes) => {
        const evaluation = evaluations.find((item) => item.horizon_minutes === minutes);
        const result = evaluation?.result ?? "pending";
        return (
          <Badge key={minutes} tone={toneFor(result)}>
            {minutes}m: {formatEvaluationResult(result)}
          </Badge>
        );
      })}
    </div>
  );
}
