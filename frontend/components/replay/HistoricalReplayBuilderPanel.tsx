"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { buildHistoricalReplay, getHistoricalReplayBuildJob } from "@/lib/api";
import type { HistoricalReplayBuildJob } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const inputClass =
  "w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white transition focus-visible:border-emerald-300 focus-visible:ring-2 focus-visible:ring-emerald-300/40";
const HISTORICAL_INTERVAL_MS = 5 * 60 * 1000;

export function HistoricalReplayBuilderPanel({ onBuilt }: { onBuilt: () => Promise<void> | void }) {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [fixtureId, setFixtureId] = useState("");
  const [scenarioName, setScenarioName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [job, setJob] = useState<HistoricalReplayBuildJob>();
  const notifiedJobRef = useRef<string | null>(null);

  const fieldError = useMemo(() => validateRange(start, end), [start, end]);
  const estimate = useMemo(() => estimateRange(start, end), [start, end]);
  const jobId = job?.job_id;
  const jobStatus = job?.status;
  const buildActive = isActiveBuild(job);

  const refreshJob = useCallback(
    async (jobId: string) => {
      try {
        const nextJob = await getHistoricalReplayBuildJob(jobId);
        setJob(nextJob);
        if (nextJob.status === "completed" && notifiedJobRef.current !== nextJob.job_id) {
          notifiedJobRef.current = nextJob.job_id;
          await onBuilt();
        }
        if (nextJob.status === "failed") {
          setError(nextJob.error ?? "Historical replay build failed.");
        }
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Historical replay build status unavailable.");
      }
    },
    [onBuilt]
  );

  useEffect(() => {
    if (!jobId || (jobStatus !== "queued" && jobStatus !== "running")) return;

    void refreshJob(jobId);
    const timer = window.setInterval(() => {
      void refreshJob(jobId);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [jobId, jobStatus, refreshJob]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validationError = validateRange(start, end);
    if (validationError) {
      setError(validationError);
      return;
    }

    setBusy(true);
    setError(undefined);
    setJob(undefined);
    notifiedJobRef.current = null;
    try {
      const response = await buildHistoricalReplay({
        start: start.trim(),
        end: end.trim(),
        fixture_id: optional(fixtureId),
        scenario_name: optional(scenarioName),
        display_name: optional(displayName),
        description: optional(description)
      });
      setJob(response);
      if (response.status === "completed") {
        notifiedJobRef.current = response.job_id;
        await onBuilt();
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Historical replay build failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Build TxLINE Historical Replay" eyebrow="Real historical data">
      <form onSubmit={submit} className="space-y-4" aria-busy={busy}>
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            id="historical-start"
            label="Start UTC"
            helper="ISO timestamp, inclusive."
            error={fieldError && !start.trim() ? "Start time is required." : undefined}
          >
            <input
              id="historical-start"
              type="text"
              value={start}
              onChange={(event) => setStart(event.target.value)}
              placeholder="2026-07-09T12:00:00Z"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={fieldError && !start.trim() ? "true" : undefined}
              aria-describedby={`historical-start-helper${
                fieldError && !start.trim() ? " historical-start-error" : ""
              }`}
              className={inputClass}
            />
          </Field>

          <Field
            id="historical-end"
            label="End UTC"
            helper="ISO timestamp, exclusive."
            error={fieldError && !end.trim() ? "End time is required." : undefined}
          >
            <input
              id="historical-end"
              type="text"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              placeholder="2026-07-09T12:30:00Z"
              autoComplete="off"
              spellCheck={false}
              aria-invalid={fieldError && !end.trim() ? "true" : undefined}
              aria-describedby={`historical-end-helper${
                fieldError && !end.trim() ? " historical-end-error" : ""
              }`}
              className={inputClass}
            />
          </Field>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field id="historical-fixture" label="Fixture ID" helper="Optional TxLINE fixture filter.">
            <input
              id="historical-fixture"
              type="text"
              inputMode="numeric"
              value={fixtureId}
              onChange={(event) => setFixtureId(event.target.value)}
              placeholder="18143850"
              autoComplete="off"
              spellCheck={false}
              className={inputClass}
            />
          </Field>

          <Field
            id="historical-scenario-name"
            label="Scenario file name"
            helper="Optional file stem. Blank uses a generated name."
          >
            <input
              id="historical-scenario-name"
              type="text"
              value={scenarioName}
              onChange={(event) => setScenarioName(event.target.value)}
              placeholder="txline_fixture_18143850_history"
              autoComplete="off"
              spellCheck={false}
              className={inputClass}
            />
          </Field>
        </div>

        <Field id="historical-display-name" label="Display name" helper="Optional label shown in replay controls.">
          <input
            id="historical-display-name"
            type="text"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder="TxLINE historical fixture 18143850"
            autoComplete="off"
            spellCheck={false}
            className={inputClass}
          />
        </Field>

        <Field id="historical-description" label="Description" helper="Optional scenario metadata.">
          <textarea
            id="historical-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            placeholder="Real TxLINE historical odds and score interval replay."
            spellCheck
            className={`${inputClass} resize-y`}
          />
        </Field>

        {estimate && <RangeEstimate estimate={estimate} />}

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={busy || buildActive} aria-busy={busy || buildActive}>
            {busy ? "Starting..." : buildActive ? "Building..." : "Build historical replay"}
          </Button>
          <p className="text-xs leading-5 text-muted">
            Uses configured `TXLINE_GUEST_JWT` and `TXLINE_API_TOKEN` on the backend.
          </p>
        </div>

        {error && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-rose-400/30 bg-rose-500/10 p-3 text-sm text-rose-100">
            <p>{error}</p>
            {job?.job_id && (
              <Button
                type="button"
                variant="secondary"
                onClick={() => void refreshJob(job.job_id)}
                className="min-h-10"
              >
                Refresh status
              </Button>
            )}
          </div>
        )}

        {job && <BuildJobStatus job={job} />}
      </form>
    </Card>
  );
}

function Field({
  id,
  label,
  helper,
  error,
  children
}: {
  id: string;
  label: string;
  helper: string;
  error?: string;
  children: ReactNode;
}) {
  const helperId = `${id}-helper`;
  const errorId = `${id}-error`;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-slate-200">
        {label}
      </label>
      {children}
      <p id={helperId} className="text-xs leading-5 text-muted">
        {helper}
      </p>
      {error && (
        <p id={errorId} className="text-xs leading-5 text-rose-200">
          {error}
        </p>
      )}
    </div>
  );
}

function RangeEstimate({
  estimate
}: {
  estimate: { intervals: number; requests: number; durationMs: number; large: boolean };
}) {
  return (
    <div
      className={`rounded-md border p-4 ${
        estimate.large
          ? "border-amber-400/30 bg-amber-400/10"
          : "border-slate-700 bg-slate-950/50"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p
          className={`text-sm font-semibold ${
            estimate.large ? "text-amber-100" : "text-slate-100"
          }`}
        >
          Estimated historical fetch
        </p>
        {estimate.large && (
          <span className="rounded-full border border-amber-300/40 px-2.5 py-1 text-xs font-semibold uppercase tracking-wide text-amber-100">
            Large range
          </span>
        )}
      </div>
      <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
        <Metric label="5m intervals" value={formatInteger(estimate.intervals)} />
        <Metric label="TxLINE requests" value={formatInteger(estimate.requests)} />
        <Metric label="Range" value={formatDuration(estimate.durationMs)} />
      </dl>
      {estimate.large && (
        <p className="mt-3 text-xs leading-5 text-amber-100/80">
          This range will take time because each interval fetches odds and scores separately.
        </p>
      )}
    </div>
  );
}

function BuildJobStatus({ job }: { job: HistoricalReplayBuildJob }) {
  const requested = job.intervals_requested ?? 0;
  const completed = job.intervals_completed ?? 0;
  const progress = requested > 0 ? Math.min(100, Math.round((completed / requested) * 100)) : 0;
  const active = isActiveBuild(job);
  const failed = job.status === "failed";
  const completedStatus = job.status === "completed";

  return (
    <div
      className={`rounded-md border p-4 ${
        failed
          ? "border-rose-400/30 bg-rose-500/10"
          : completedStatus
            ? "border-emerald-400/30 bg-emerald-400/10"
            : "border-sky-400/30 bg-sky-400/10"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-white">
            {completedStatus
              ? `Built ${job.scenario_name ?? "historical replay"}`
              : failed
                ? "Historical build failed"
                : "Historical build running"}
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">Job {shortJobId(job.job_id)}</p>
        </div>
        <span
          className={`rounded-full border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${
            failed
              ? "border-rose-300/40 text-rose-100"
              : completedStatus
                ? "border-emerald-300/40 text-emerald-100"
                : "border-sky-300/40 text-sky-100"
          }`}
        >
          {job.status}
        </span>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between gap-3 text-xs text-muted">
          <span>
            {formatInteger(completed)} / {requested ? formatInteger(requested) : "pending"} intervals
          </span>
          <span>{progress}%</span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-900">
          <div
            className={`h-full rounded-full transition-[width] duration-300 ${
              failed ? "bg-rose-300" : completedStatus ? "bg-emerald-300" : "bg-sky-300"
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Metric label="Odds events" value={formatInteger(job.odds_events ?? 0)} />
        <Metric label="Score events" value={formatInteger(job.score_events ?? 0)} />
        <Metric label="Total events" value={formatInteger(job.events_total ?? 0)} />
        <Metric label="Updated" value={formatUtc(job.updated_at)} />
      </dl>

      {active && job.current_interval_start && (
        <p className="mt-3 text-xs leading-5 text-slate-300">
          Current interval: {formatUtc(job.current_interval_start)} | epoch day{" "}
          {job.current_epoch_day ?? "n/a"} | hour {job.current_hour_of_day ?? "n/a"} | interval{" "}
          {job.current_interval ?? "n/a"}
        </p>
      )}

      {completedStatus && job.path && (
        <p className="mt-3 break-all text-xs leading-5 text-emerald-100/80">Saved to {job.path}</p>
      )}

      {failed && job.error && <p className="mt-3 text-xs leading-5 text-rose-100">{job.error}</p>}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-emerald-200/70">{label}</dt>
      <dd className="mt-1 font-semibold text-emerald-50">{value}</dd>
    </div>
  );
}

function optional(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

function validateRange(start: string, end: string) {
  if (!start.trim() || !end.trim()) return "Start and end times are required.";
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (Number.isNaN(startMs) || Number.isNaN(endMs)) {
    return "Use valid ISO timestamps, for example 2026-07-09T12:00:00Z.";
  }
  if (endMs <= startMs) return "End time must be after start time.";
  return undefined;
}

function estimateRange(start: string, end: string) {
  const startMs = Date.parse(start);
  const endMs = Date.parse(end);
  if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs <= startMs) return undefined;

  const flooredStartMs = floorToHistoricalInterval(startMs);
  const intervals = Math.max(0, Math.ceil((endMs - flooredStartMs) / HISTORICAL_INTERVAL_MS));
  const requests = intervals * 2;
  return {
    intervals,
    requests,
    durationMs: endMs - startMs,
    large: requests >= 1000
  };
}

function floorToHistoricalInterval(valueMs: number) {
  const value = new Date(valueMs);
  const minute = value.getUTCMinutes();
  value.setUTCMinutes(minute - (minute % 5), 0, 0);
  return value.getTime();
}

function isActiveBuild(job: HistoricalReplayBuildJob | undefined) {
  return job?.status === "queued" || job?.status === "running";
}

function shortJobId(jobId: string) {
  return jobId.length > 8 ? jobId.slice(0, 8) : jobId;
}

function formatInteger(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatUtc(value: string | null | undefined) {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "n/a";
  return parsed.toISOString().replace(".000Z", "Z");
}

function formatDuration(durationMs: number) {
  const totalMinutes = Math.max(0, Math.round(durationMs / 60000));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}
