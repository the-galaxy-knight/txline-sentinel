import type { Signal } from "@/lib/types";
import { EmptyState } from "@/components/ui/States";
import { SignalCard } from "./SignalCard";

export function SignalFeed({ signals }: { signals: Signal[] }) {
  if (signals.length === 0) {
    return <EmptyState message="No signals yet. Start a replay scenario to generate signals." />;
  }
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {signals.map((signal) => (
        <SignalCard key={signal.id} signal={signal} />
      ))}
    </div>
  );
}
