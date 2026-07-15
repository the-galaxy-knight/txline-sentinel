import { API_BASE_URL } from "./api";
import type { DashboardStreamEvent } from "./types";

export type SseConnection = {
  close: () => void;
};

export function connectDashboardStream(
  onEvent: (event: DashboardStreamEvent) => void,
  onStateChange?: (state: "connected" | "disconnected" | "error") => void
): SseConnection {
  const source = new EventSource(`${API_BASE_URL}/api/stream`);

  source.onopen = () => onStateChange?.("connected");
  source.onerror = () => onStateChange?.("error");

  const handleMessage = (event: MessageEvent) => {
    try {
      onEvent(JSON.parse(event.data) as DashboardStreamEvent);
    } catch {
      onEvent({ type: event.type, created_at: new Date().toISOString(), payload: {} });
    }
  };

  source.onmessage = handleMessage;
  [
    "odds_processed",
    "score_processed",
    "signal_created",
    "signal_evaluation_updated",
    "replay_status_changed"
  ].forEach((type) => source.addEventListener(type, handleMessage));

  return {
    close: () => {
      source.close();
      onStateChange?.("disconnected");
    }
  };
}
