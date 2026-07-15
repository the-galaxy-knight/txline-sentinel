"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getSignals } from "@/lib/api";
import type { Signal } from "@/lib/types";
import { SignalFeed } from "@/components/signals/SignalFeed";
import { Card } from "@/components/ui/Card";
import { ErrorState, LoadingState } from "@/components/ui/States";

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [minConfidence, setMinConfidence] = useState(0);
  const [signalType, setSignalType] = useState("");
  const [status, setStatus] = useState("");
  const [fixtureId, setFixtureId] = useState("");

  const load = useCallback(async () => {
    try {
      const response = await getSignals({
        min_confidence: minConfidence || undefined,
        signal_type: signalType || undefined,
        status: status || undefined,
        fixture_id: fixtureId || undefined,
        limit: 100
      });
      setSignals(response);
      setError(undefined);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Signals unavailable.");
    } finally {
      setLoading(false);
    }
  }, [fixtureId, minConfidence, signalType, status]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [load]);

  const types = useMemo(
    () => Array.from(new Set(signals.map((signal) => signal.signal_type).filter(Boolean))),
    [signals]
  );

  if (loading) return <LoadingState label="Loading signals..." />;

  return (
    <div className="space-y-6">
      {error && <ErrorState message={error} />}
      <div>
        <p className="text-sm uppercase tracking-wide text-emerald-300">Signal feed</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Detected market intelligence</h1>
      </div>

      <Card title="Filters" eyebrow="Narrow the feed">
        <div className="grid gap-3 md:grid-cols-4">
          <label className="text-sm">
            <span className="mb-2 block text-muted">Min confidence</span>
            <input
              type="number"
              min={0}
              max={100}
              value={minConfidence}
              onChange={(event) => setMinConfidence(Number(event.target.value))}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            />
          </label>
          <label className="text-sm">
            <span className="mb-2 block text-muted">Signal type</span>
            <select value={signalType} onChange={(event) => setSignalType(event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white">
              <option value="">All types</option>
              {types.map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-2 block text-muted">Status</span>
            <select value={status} onChange={(event) => setStatus(event.target.value)} className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white">
              <option value="">All statuses</option>
              <option value="new">new</option>
              <option value="evaluating">evaluating</option>
              <option value="evaluated">evaluated</option>
              <option value="alerted">alerted</option>
            </select>
          </label>
          <label className="text-sm">
            <span className="mb-2 block text-muted">Fixture ID</span>
            <input
              value={fixtureId}
              onChange={(event) => setFixtureId(event.target.value)}
              className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white"
              placeholder="demo-arg-fra-001"
            />
          </label>
        </div>
      </Card>

      <SignalFeed signals={signals} />
    </div>
  );
}
