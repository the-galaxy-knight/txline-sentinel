export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 text-sm text-muted">{label}</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="rounded-lg border border-rose-400/30 bg-rose-500/10 p-4 text-sm text-rose-100">{message}</div>;
}

export function EmptyState({ message }: { message: string }) {
  return <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 text-sm text-muted">{message}</div>;
}
