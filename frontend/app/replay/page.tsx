"use client";

import { useCallback, useEffect, useState } from "react";
import { getLatestSignals, getReplayScenarios, getReplayStatus } from "@/lib/api";
import type { ReplayScenario, ReplayStatus, Signal } from "@/lib/types";
import { HistoricalReplayBuilderPanel } from "@/components/replay/HistoricalReplayBuilderPanel";
import { ReplayControlPanel } from "@/components/replay/ReplayControlPanel";
import { ReplayStatusCard } from "@/components/replay/ReplayStatusCard";
import { SignalFeed } from "@/components/signals/SignalFeed";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { SourceModeBadge } from "@/components/ui/Badge";

export default function ReplayPage() {
  const [scenarios, setScenarios] = useState<ReplayScenario[]>([]);
  const [replay, setReplay] = useState<ReplayStatus>();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  const load = useCallback(async () => {
    try {
      const [scenarioResponse, replayResponse, signalResponse] = await Promise.all([
        getReplayScenarios(),
        getReplayStatus(),
        getLatestSignals(10)
      ]);
      setScenarios(scenarioResponse);
      setReplay(replayResponse);
      setSignals(signalResponse);
      setError(undefined);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Replay data unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 3000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (loading) return <LoadingState label="Loading replay controls..." />;

  return (
    <div className="space-y-6">
      {error && <ErrorState message={error} />}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm uppercase tracking-wide text-emerald-300">Replay control room</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">Run the signal pipeline</h1>
        </div>
        <SourceModeBadge mode={replay?.status && replay.status !== "idle" ? "replay" : "disabled"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-6">
          <ReplayControlPanel scenarios={scenarios} replay={replay} onChanged={load} />
          <HistoricalReplayBuilderPanel onBuilt={load} />
        </div>
        <ReplayStatusCard replay={replay} />
      </div>

      <Card title="Latest replay signals" eyebrow="Generated during demo">
        <SignalFeed signals={signals} />
      </Card>

      <Card title="What judges should notice" eyebrow="Architecture proof">
        <p className="text-sm leading-6 text-slate-300">
          Replay mode is not a mocked dashboard. It invokes the same normalization, market state,
          detection, explanation, persistence, evaluation, alert, and SSE pipeline used by live
          TxLINE ingestion.
        </p>
      </Card>
    </div>
  );
}
