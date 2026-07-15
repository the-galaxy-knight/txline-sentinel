"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getReplayStatus, getRuntimeSettings } from "@/lib/api";
import type { ReplayStatus, RuntimeSettings } from "@/lib/types";
import { SourceModeBadge, StatusBadge } from "@/components/ui/Badge";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/replay", label: "Replay" },
  { href: "/signals", label: "Signals" },
  { href: "/matches", label: "Matches" }
];

function effectiveMode(runtime?: RuntimeSettings, replay?: ReplayStatus) {
  if (replay?.status && replay.status !== "idle") return "replay";
  return runtime?.ingestion_mode ?? "disabled";
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [runtime, setRuntime] = useState<RuntimeSettings>();
  const [replay, setReplay] = useState<ReplayStatus>();

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [settings, replayStatus] = await Promise.all([
          getRuntimeSettings(),
          getReplayStatus()
        ]);
        if (mounted) {
          setRuntime(settings);
          setReplay(replayStatus);
        }
      } catch {
        if (mounted) {
          setRuntime({ ingestion_mode: "unknown" });
        }
      }
    };
    load();
    const timer = window.setInterval(load, 5000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  const mode = effectiveMode(runtime, replay);

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-800 bg-slate-950/80 px-5 py-6 lg:block">
        <Link href="/" className="block">
          <p className="text-sm uppercase tracking-wide text-emerald-300">TxLINE Sentinel</p>
          <h1 className="mt-2 text-xl font-semibold text-white">Odds Intelligence Agent</h1>
        </Link>
        <nav className="mt-8 space-y-2">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-slate-900 hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 rounded-lg border border-slate-800 bg-slate-900/70 p-4">
          <p className="mb-2 text-xs uppercase tracking-wide text-muted">Current data source</p>
          <SourceModeBadge mode={mode} />
          <p className="mt-3 text-xs text-muted">
            Configured ingestion: {(runtime?.ingestion_mode ?? "unknown").toUpperCase()}
          </p>
          <p className="mt-1 text-xs text-muted">
            Replay status: {(replay?.status ?? "unknown").toUpperCase()}
          </p>
        </div>
      </aside>

      <main className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/88 px-4 py-4 backdrop-blur lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-muted">Autonomous World Cup Odds Intelligence Agent</p>
              <h2 className="text-xl font-semibold text-white">TxLINE Sentinel</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs uppercase tracking-wide text-muted">Data source</span>
              <SourceModeBadge mode={mode} />
              <StatusBadge value={runtime?.txline_configured ?? false} />
            </div>
          </div>
        </header>
        <div className="px-4 py-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
