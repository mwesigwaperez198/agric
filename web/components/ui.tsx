import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700",
  in_escrow: "bg-blue-100 text-blue-700",
  shipped: "bg-cyan-100 text-cyan-700",
  delivered: "bg-emerald-100 text-emerald-700",
  settled: "bg-emerald-100 text-emerald-700",
  disputed: "bg-red-100 text-red-700",
  cancelled: "bg-slate-200 text-slate-500",
  active: "bg-emerald-100 text-emerald-700",
  sold_out: "bg-slate-200 text-slate-500",
  paused: "bg-amber-100 text-amber-700",
  safe: "bg-emerald-100 text-emerald-700",
  watch: "bg-amber-100 text-amber-700",
  warning: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize",
        STATUS_STYLES[status] ?? "bg-slate-100 text-slate-600"
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
      {status.replace("_", " ")}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center justify-center py-10", className)}>
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-brand-500" />
    </div>
  );
}

export function EmptyState({ icon, title, message }: { icon: string; title: string; message?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
      <div className="rounded-full bg-slate-100 p-3 text-slate-400">
        {/* icon fallback */}
        <span className="block h-6 w-6" />
      </div>
      <h3 className="font-semibold text-slate-700">{title}</h3>
      {message && <p className="max-w-sm text-sm text-slate-500">{message}</p>}
    </div>
  );
}
