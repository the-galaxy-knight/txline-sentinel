"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getMatchSignals, getMatchState, getOddsEvents, getScoreEvents } from "@/lib/api";
import type { MatchState, OddsEvent, ScoreEvent, Signal } from "@/lib/types";
import { MatchStateCard } from "@/components/matches/MatchStateCard";
import { OddsMovementChart } from "@/components/matches/OddsMovementChart";
import { EventTimeline } from "@/components/matches/EventTimeline";
import { SignalFeed } from "@/components/signals/SignalFeed";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";

export default function MatchDetailPage() {
  const params = useParams<{ fixtureId: string }>();
  const [state, setState] = useState<MatchState>();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [odds, setOdds] = useState<OddsEvent[]>([]);
  const [scores, setScores] = useState<ScoreEvent[]>([]);
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params.fixtureId) return;
    Promise.all([
      getMatchState(params.fixtureId),
      getMatchSignals(params.fixtureId),
      getOddsEvents({ fixture_id: params.fixtureId, limit: 100 }),
      getScoreEvents({ fixture_id: params.fixtureId, limit: 100 })
    ])
      .then(([stateResponse, signalResponse, oddsResponse, scoreResponse]) => {
        setState(stateResponse);
        setSignals(signalResponse);
        setOdds(oddsResponse);
        setScores(scoreResponse);
        setError(undefined);
      })
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Match state unavailable."))
      .finally(() => setLoading(false));
  }, [params.fixtureId]);

  if (loading) return <LoadingState label="Loading match state..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm uppercase tracking-wide text-emerald-300">Fixture {params.fixtureId}</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Match intelligence view</h1>
      </div>
      <MatchStateCard state={state} />
      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <OddsMovementChart oddsEvents={odds.length ? odds : state?.latest_odds} />
        <Card title="Latest fixture signals" eyebrow="Per-match feed">
          <SignalFeed signals={signals.length ? signals : state?.latest_signals ?? []} />
        </Card>
      </div>
      <EventTimeline oddsEvents={odds} scoreEvents={scores} />
    </div>
  );
}
