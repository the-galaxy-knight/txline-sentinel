"use client";

import { useEffect, useState } from "react";
import type { ReplayScenario, ReplayStatus } from "@/lib/types";
import { pauseReplay, resetReplay, resumeReplay, startReplay, stopReplay } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";

const speeds = [1, 5, 10, 30, 60];

export function ReplayControlPanel({
  scenarios,
  replay,
  onChanged
}: {
  scenarios: ReplayScenario[];
  replay?: ReplayStatus;
  onChanged: () => void;
}) {
  const [scenarioName, setScenarioName] = useState(scenarios[0]?.name ?? "");
  const [speed, setSpeed] = useState(30);
  const [resetDatabase, setResetDatabase] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!scenarios.length) {
      setScenarioName("");
      return;
    }
    if (!scenarios.some((scenario) => scenario.name === scenarioName)) {
      setScenarioName(scenarios[0].name);
    }
  }, [scenarioName, scenarios]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(undefined);
    try {
      await action();
      await onChanged();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Replay action failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Replay Control Panel" eyebrow="Judge demo" action={<StatusBadge value={replay?.status ?? "idle"} />}>
      <div className="grid gap-4 md:grid-cols-[1fr_10rem]">
        <label className="text-sm">
          <span className="mb-2 block text-muted">Scenario</span>
          <select
            value={scenarioName}
            onChange={(event) => setScenarioName(event.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          >
            {scenarios.map((scenario) => (
              <option key={scenario.name} value={scenario.name}>
                {scenario.display_name ?? scenario.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-2 block text-muted">Speed</span>
          <select
            value={speed}
            onChange={(event) => setSpeed(Number(event.target.value))}
            className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-white"
          >
            {speeds.map((value) => (
              <option key={value} value={value}>
                {value}x
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-4 flex items-center gap-2 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={resetDatabase}
          onChange={(event) => setResetDatabase(event.target.checked)}
        />
        Reset database before start
      </label>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button
          disabled={busy || !scenarioName}
          onClick={() =>
            run(() =>
              startReplay({
                scenario_name: scenarioName,
                speed_multiplier: speed,
                reset_database: resetDatabase
              })
            )
          }
        >
          Start replay
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => run(pauseReplay)}>
          Pause
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => run(resumeReplay)}>
          Resume
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => run(stopReplay)}>
          Stop
        </Button>
        <Button variant="danger" disabled={busy} onClick={() => run(resetReplay)}>
          Reset
        </Button>
      </div>

      {error && <p className="mt-4 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">{error}</p>}
    </Card>
  );
}
