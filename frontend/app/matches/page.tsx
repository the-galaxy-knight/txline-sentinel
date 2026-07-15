"use client";

import { useEffect, useState } from "react";
import { getMatches } from "@/lib/api";
import type { Fixture } from "@/lib/types";
import { MatchList } from "@/components/matches/MatchList";
import { ErrorState, LoadingState } from "@/components/ui/States";

export default function MatchesPage() {
  const [matches, setMatches] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  useEffect(() => {
    getMatches()
      .then((response) => {
        setMatches(response);
        setError(undefined);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Matches unavailable."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingState label="Loading matches..." />;

  return (
    <div className="space-y-6">
      {error && <ErrorState message={error} />}
      <div>
        <p className="text-sm uppercase tracking-wide text-emerald-300">Match state</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Fixtures and tracked markets</h1>
      </div>
      <MatchList matches={matches} />
    </div>
  );
}
