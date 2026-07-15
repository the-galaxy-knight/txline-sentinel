export function formatProbability(value?: number | null) {
  if (value === undefined || value === null) return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatProbabilityDelta(value?: number | null) {
  if (value === undefined || value === null) return "n/a";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)} pp`;
}

export function formatConfidence(value?: number | null) {
  if (value === undefined || value === null) return "n/a";
  return `${Math.round(value)}/100`;
}

export function formatDateTime(value?: string | null) {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "n/a";
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

export function formatSignalType(value?: string | null) {
  if (!value) return "Unknown signal";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatDirection(value?: string | null) {
  if (!value) return "Flat";
  return value === "up" ? "Up" : value === "down" ? "Down" : value;
}

export function formatEvaluationResult(value?: string | null) {
  if (!value) return "Pending";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function formatSourceMode(value?: string | null) {
  if (!value) return "Unknown";
  return value.toUpperCase();
}

export function compactNumber(value?: number | null) {
  if (value === undefined || value === null) return "0";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value);
}
