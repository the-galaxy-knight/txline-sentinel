import type {
  DashboardStreamEvent,
  Fixture,
  HealthResponse,
  HistoricalReplayBuildJob,
  HistoricalReplayBuildRequest,
  MatchState,
  OddsEvent,
  ReplayScenario,
  ReplayStartRequest,
  ReplayStatus,
  RuntimeSettings,
  ScoreEvent,
  Signal
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type QueryValue = string | number | boolean | null | undefined;

function buildUrl(path: string, params?: Record<string, QueryValue>) {
  const url = new URL(path, `${API_BASE_URL}/`);
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  params?: Record<string, QueryValue>
): Promise<T> {
  const response = await fetch(buildUrl(path, params), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(`${path} failed with HTTP ${response.status}${detail ? `: ${detail}` : ""}`);
  }

  return response.json() as Promise<T>;
}

export async function getHealth() {
  return request<HealthResponse>("/health");
}

export async function getRuntimeSettings() {
  return request<RuntimeSettings>("/api/settings/runtime");
}

export async function getReplayScenarios() {
  return request<ReplayScenario[]>("/api/replay/scenarios");
}

export async function getReplayStatus() {
  return request<ReplayStatus>("/api/replay/status");
}

export async function startReplay(payload: ReplayStartRequest) {
  return request<{ status?: string; message?: string; active_run?: ReplayStatus["active_run"] }>(
    "/api/replay/start",
    { method: "POST", body: JSON.stringify(payload) }
  );
}

export async function pauseReplay() {
  return request("/api/replay/pause", { method: "POST" });
}

export async function resumeReplay() {
  return request("/api/replay/resume", { method: "POST" });
}

export async function stopReplay() {
  return request("/api/replay/stop", { method: "POST" });
}

export async function resetReplay() {
  return request("/api/replay/reset", { method: "POST" });
}

export async function buildHistoricalReplay(payload: HistoricalReplayBuildRequest) {
  return request<HistoricalReplayBuildJob>("/api/replay/historical/build", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function getHistoricalReplayBuildJob(jobId: string) {
  return request<HistoricalReplayBuildJob>(`/api/replay/historical/build/${jobId}`);
}

export async function getSignals(params?: {
  fixture_id?: string;
  signal_type?: string;
  status?: string;
  min_confidence?: number;
  limit?: number;
}) {
  return request<Signal[]>("/api/signals", {}, params);
}

export async function getLatestSignals(limit = 10) {
  return request<Signal[]>("/api/signals/latest", {}, { limit });
}

export async function getHighConfidenceSignals(threshold = 80) {
  return request<Signal[]>("/api/signals/high-confidence", {}, { threshold });
}

export async function getSignal(id: string | number) {
  return request<Signal>(`/api/signals/${id}`);
}

export async function getMatches() {
  return request<Fixture[]>("/api/matches");
}

export async function getMatchState(fixtureId: string) {
  return request<MatchState>(`/api/matches/${fixtureId}/state`);
}

export async function getMatchSignals(fixtureId: string) {
  return request<Signal[]>(`/api/matches/${fixtureId}/signals`);
}

export async function getOddsEvents(params?: { fixture_id?: string; limit?: number }) {
  return request<OddsEvent[]>("/api/events/odds", {}, params);
}

export async function getScoreEvents(params?: { fixture_id?: string; limit?: number }) {
  return request<ScoreEvent[]>("/api/events/scores", {}, params);
}

export type ApiSnapshot = {
  health?: HealthResponse;
  runtime?: RuntimeSettings;
  replay?: ReplayStatus;
  latestSignals?: Signal[];
  highConfidenceSignals?: Signal[];
  streamEvents?: DashboardStreamEvent[];
};
