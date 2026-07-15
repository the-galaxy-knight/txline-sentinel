import { formatSourceMode } from "@/lib/format";

const toneClasses: Record<string, string> = {
  green: "border-emerald-400/35 bg-emerald-400/10 text-emerald-200",
  red: "border-rose-400/35 bg-rose-400/10 text-rose-200",
  amber: "border-amber-400/35 bg-amber-400/10 text-amber-200",
  blue: "border-sky-400/35 bg-sky-400/10 text-sky-200",
  gray: "border-slate-500/35 bg-slate-500/10 text-slate-200",
  violet: "border-violet-400/35 bg-violet-400/10 text-violet-200"
};

export function Badge({
  children,
  tone = "gray"
}: {
  children: React.ReactNode;
  tone?: keyof typeof toneClasses;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-semibold ${toneClasses[tone]}`}
    >
      {children}
    </span>
  );
}

export function SourceModeBadge({ mode }: { mode?: string | null }) {
  const normalized = (mode || "unknown").toLowerCase();
  const tone =
    normalized === "live"
      ? "green"
      : normalized === "snapshot"
        ? "blue"
        : normalized === "replay"
          ? "violet"
          : normalized === "disabled"
            ? "gray"
            : "amber";
  return <Badge tone={tone}>{formatSourceMode(mode)}</Badge>;
}

export function StatusBadge({ value }: { value?: string | boolean | null }) {
  if (typeof value === "boolean") {
    return <Badge tone={value ? "green" : "gray"}>{value ? "Configured" : "Not configured"}</Badge>;
  }
  const normalized = (value || "unknown").toLowerCase();
  const tone =
    normalized === "running" || normalized === "ok" || normalized === "healthy"
      ? "green"
      : normalized === "failed" || normalized === "error"
        ? "red"
        : normalized === "pending" ||
            normalized === "evaluating" ||
            normalized === "paused" ||
            normalized === "connecting" ||
            normalized === "degraded"
          ? "amber"
          : "gray";
  return <Badge tone={tone}>{value || "Unknown"}</Badge>;
}
