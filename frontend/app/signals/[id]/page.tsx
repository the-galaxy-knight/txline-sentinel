"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getSignal } from "@/lib/api";
import type { Signal } from "@/lib/types";
import { SignalDetail } from "@/components/signals/SignalDetail";
import { ErrorState, LoadingState } from "@/components/ui/States";

export default function SignalDetailPage() {
  const params = useParams<{ id: string }>();
  const [signal, setSignal] = useState<Signal>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!params.id) return;
    getSignal(params.id)
      .then(setSignal)
      .catch((exc) => setError(exc instanceof Error ? exc.message : "Signal unavailable."));
  }, [params.id]);

  if (error) return <ErrorState message={error} />;
  if (!signal) return <LoadingState label="Loading signal detail..." />;

  return <SignalDetail signal={signal} />;
}
