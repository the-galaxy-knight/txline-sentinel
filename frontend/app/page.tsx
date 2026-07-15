"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getHealth,
  getHighConfidenceSignals,
  getLatestSignals,
  getReplayScenarios,
  getReplayStatus,
  getRuntimeSettings
} from "@/lib/api";
import { connectDashboardStream } from "@/lib/sse";
import type {
  DashboardStreamEvent,
  HealthResponse,
  ReplayScenario,
  ReplayStatus,
  RuntimeSettings,
  Signal
} from "@/lib/types";
import { StatusCards } from "@/components/dashboard/StatusCards";
import { AgentTimeline } from "@/components/dashboard/AgentTimeline";
import { LiveHealthPanel } from "@/components/dashboard/LiveHealthPanel";
import { ReplayControlPanel } from "@/components/replay/ReplayControlPanel";
import { SignalFeed } from "@/components/signals/SignalFeed";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";
import { SourceModeBadge, StatusBadge } from "@/components/ui/Badge";

export default function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse>();
  const [runtime, setRuntime] = useState<RuntimeSettings>();
  const [replay, setReplay] = useState<ReplayStatus>();
  const [scenarios, setScenarios] = useState<ReplayScenario[]>([]);
  const [latestSignals, setLatestSignals] = useState<Signal[]>([]);
  const [highConfidenceSignals, setHighConfidenceSignals] = useState<Signal[]>([]);
  const [events, setEvents] = useState<DashboardStreamEvent[]>([]);
  const [streamState, setStreamState] = useState<"connected" | "disconnected" | "error">("disconnected");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();

  const load = useCallback(async () => {
    try {
      const [healthResponse, runtimeResponse, replayResponse, scenarioResponse, latest, high] =
        await Promise.all([
          getHealth(),
          getRuntimeSettings(),
          getReplayStatus(),
          getReplayScenarios(),
          getLatestSignals(8),
          getHighConfidenceSignals(80)
        ]);
      setHealth(healthResponse);
      setRuntime(runtimeResponse);
      setReplay(replayResponse);
      setScenarios(scenarioResponse);
      setLatestSignals(latest);
      setHighConfidenceSignals(high);
      setError(undefined);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Backend unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 4000);
    const connection = connectDashboardStream(
      (event) => {
        setEvents((current) => [event, ...current].slice(0, 40));
        if (
          ["signal_created", "signal_evaluation_updated", "replay_status_changed"].includes(
            event.type ?? ""
          )
        ) {
          load();
        }
      },
      (state) => setStreamState(state)
    );
    return () => {
      window.clearInterval(timer);
      connection.close();
    };
  }, [load]);

  if (loading) return <LoadingState label="Loading TxLINE Sentinel dashboard..." />;

  const currentMode = replay?.status && replay.status !== "idle" ? "replay" : runtime?.ingestion_mode;

  return (
    <div className="space-y-6">
      {error && <ErrorState message={`Backend unavailable. Make sure FastAPI is running. ${error}`} />}

      <section className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <div>
          <p className="text-sm uppercase tracking-wide text-emerald-300">Trading Tools and Agents</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">TxLINE Sentinel</h1>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
            Autonomous World Cup odds intelligence: ingest events, detect probability movement,
            explain signals, and track whether each signal followed through.
          </p>
        </div>
        <Card>
          <p className="text-xs uppercase tracking-wide text-muted">Current source mode</p>
          <div className="mt-3 flex items-center gap-3">
            <SourceModeBadge mode={currentMode} />
            <StatusBadge value={runtime?.txline_configured ?? false} />
          </div>
          <p className="mt-3 text-sm text-muted">
            This UI distinguishes configured ingestion mode from per-event `source_mode` on every
            signal and event row.
          </p>
        </Card>
      </section>

      <StatusCards
        health={health}
        runtime={runtime}
        replay={replay}
        signals={latestSignals}
        highConfidence={highConfidenceSignals}
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_24rem]">
        <div className="space-y-6">
          <Card title="Latest Signals" eyebrow="Agent output">
            <SignalFeed signals={latestSignals} />
          </Card>
          <AgentTimeline events={events} streamState={streamState} />
        </div>
        <div className="space-y-6">
          <LiveHealthPanel runtime={runtime} />
          <ReplayControlPanel scenarios={scenarios} replay={replay} onChanged={load} />
          <Card title="What judges should notice" eyebrow="Replay equals pipeline">
            <p className="text-sm leading-6 text-slate-300">
              Replay mode sends market and score events through the same backend processor used by
              live TxLINE ingestion. The source badge shows whether the current data came from
              `REPLAY`, `SNAPSHOT`, or `LIVE`.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
