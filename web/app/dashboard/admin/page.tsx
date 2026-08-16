"use client";

import { useState } from "react";
import { useRequireRole } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { apiFetch } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney, getErrorMessage } from "@/lib/utils";

interface Stats {
  users: number;
  listings: number;
  orders: number;
  escrow_entries: number;
  biosensor_readings: number;
  commission_total: number;
}

interface ThreatSummary {
  threat_levels: Record<string, number>;
  total: number;
}

export default function AdminDashboard() {
  useRequireRole(["admin"]);
  const stats = useApi<Stats>("/admin/stats");
  const threats = useApi<ThreatSummary>("/admin/threats/summary");
  const [orderId, setOrderId] = useState("");
  const [verifyResult, setVerifyResult] = useState<{ verified: boolean; broken_at?: number } | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  async function verifyLedger(e: React.FormEvent) {
    e.preventDefault();
    setVerifyError(null);
    setVerifyResult(null);
    try {
      const res = await apiFetch<{ verified: boolean; broken_at?: number }>(`/admin/ledger/verify/${orderId}`);
      setVerifyResult(res);
    } catch (err) {
      setVerifyError(getErrorMessage(err));
    }
  }

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Platform admin</h1>
        <p className="text-sm text-slate-500">NOVARA platform operations — tamper-evident by design.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.data &&
          [
            { label: "Users", value: stats.data.users },
            { label: "Listings", value: stats.data.listings },
            { label: "Orders", value: stats.data.orders },
            { label: "Escrow ledger entries", value: stats.data.escrow_entries },
            { label: "Biosensor readings", value: stats.data.biosensor_readings },
            { label: "Commission collected", value: formatMoney(stats.data.commission_total, "UGX") },
          ].map((s) => (
            <div key={s.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">{s.label}</p>
              <p className="mt-1 text-2xl font-bold text-slate-900">{s.value}</p>
            </div>
          ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="shield" className="h-4 w-4 text-brand-600" /> Ledger integrity check
          </h2>
          <form onSubmit={verifyLedger} className="flex gap-2">
            <input
              inputMode="numeric"
              value={orderId}
              onChange={(e) => setOrderId(e.target.value.replace(/\D/g, ""))}
              placeholder="Order ID"
              className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
            />
            <button type="submit" className="rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700">
              Verify
            </button>
          </form>
          {verifyError && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{verifyError}</p>}
          {verifyResult && (
            <p className={`mt-3 rounded-xl px-3 py-2 text-sm font-medium ${verifyResult.verified ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
              {verifyResult.verified
                ? "SHA-256 chain verified — ledger is tamper-evident."
                : `Integrity breach detected at entry ${verifyResult.broken_at}.`}
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="activity" className="h-4 w-4 text-brand-600" /> Threat summary
          </h2>
          {threats.loading ? (
            <Spinner />
          ) : threats.data ? (
            <div className="space-y-2">
              {Object.entries(threats.data.threat_levels).map(([level, count]) => (
                <div key={level} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                  <span className="font-medium capitalize text-slate-700">{level}</span>
                  <span className="font-bold text-slate-900">{count}</span>
                </div>
              ))}
              <p className="pt-1 text-xs text-slate-400">{threats.data.total} total readings</p>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No biosensor data yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
