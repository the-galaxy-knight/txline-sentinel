"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import type { OddsEvent } from "@/lib/types";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/States";

export function OddsMovementChart({ oddsEvents = [] }: { oddsEvents?: OddsEvent[] }) {
  const data = oddsEvents
    .filter((event) => event.implied_probability !== null && event.implied_probability !== undefined)
    .slice()
    .reverse()
    .map((event, index) => ({
      index: index + 1,
      probability: Number(((event.implied_probability ?? 0) * 100).toFixed(2)),
      outcome: event.outcome_name ?? "Outcome"
    }));

  return (
    <Card title="Odds Movement" eyebrow="Implied probability">
      {data.length === 0 ? (
        <EmptyState message="No odds movement available for this fixture yet." />
      ) : (
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid stroke="#263244" strokeDasharray="3 3" />
              <XAxis dataKey="index" stroke="#8fa0b7" />
              <YAxis stroke="#8fa0b7" domain={["auto", "auto"]} unit="%" />
              <Tooltip contentStyle={{ background: "#10151f", border: "1px solid #263244" }} />
              <Line type="monotone" dataKey="probability" stroke="#26d7a1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
