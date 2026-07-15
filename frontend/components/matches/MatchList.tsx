import Link from "next/link";
import type { Fixture } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/Badge";

export function MatchList({ matches }: { matches: Fixture[] }) {
  if (matches.length === 0) {
    return <EmptyState message="No matches found. Use replay mode or TxLINE ingestion to populate fixtures." />;
  }
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {matches.map((match) => (
        <Card key={match.fixture_id ?? match.id} title={`${match.participant_1 ?? "TBD"} vs ${match.participant_2 ?? "TBD"}`} eyebrow={match.fixture_id}>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge value={match.status ?? "scheduled"} />
            <span className="text-sm text-muted">{match.competition_id ?? "competition unknown"}</span>
          </div>
          <p className="mt-3 text-sm text-muted">Start: {formatDateTime(match.start_time)}</p>
          <Link href={`/matches/${match.fixture_id}`} className="mt-4 inline-block text-sm font-semibold text-emerald-300 hover:text-emerald-200">
            Open match state
          </Link>
        </Card>
      ))}
    </div>
  );
}
