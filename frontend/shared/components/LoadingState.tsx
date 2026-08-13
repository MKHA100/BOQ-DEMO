export function LoadingState({ label = "Loading" }: { label?: string }) {
  return <div className="rounded-lg border border-border bg-panel p-4 text-sm text-muted">{label}</div>;
}
