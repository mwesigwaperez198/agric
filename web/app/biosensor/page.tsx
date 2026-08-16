"use client";

import { useState } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { StatusBadge, Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatDateTime, getErrorMessage, timeAgo } from "@/lib/utils";

interface Reading {
  id: number;
  device_id: string;
  crop_name: string;
  batch_id?: string | null;
  payload: Record<string, number | boolean | string>;
  threat_level: string;
  threats: Array<{ code: string; label: string; level: string; value?: number; limit?: number; message?: string }>;
  risk_score: number;
  received_at: string;
}

const THRESHOLDS: Record<string, Record<string, number>> = {
  coffee: { ochratoxin_A_ppb: 2.0, moisture_pct: 12.5 },
  maize: { aflatoxin_B1_ppb: 10.0, moisture_pct: 13.5 },
};

const RISK_COLORS: Record<string, { ring: string; text: string; label: string }> = {
  safe: { ring: "#10b981", text: "text-emerald-600", label: "SAFE" },
  watch: { ring: "#f59e0b", text: "text-amber-600", label: "WATCH" },
  warning: { ring: "#f97316", text: "text-orange-600", label: "WARNING" },
  critical: { ring: "#ef4444", text: "text-red-600", label: "CRITICAL" },
};

function generateMockPayload(crop: string, contamination: string) {
  const t = THRESHOLDS[crop] ?? THRESHOLDS.coffee;
  const factor = { low: 0.6, moderate: 1.3, severe: 2.4 }[contamination as "low" | "moderate" | "severe"] ?? 0.6;
  const payload: Record<string, number | boolean> = {
    temperature_c: +(22 + (Math.random() - 0.5) * 6).toFixed(1),
    humidity_pct: +(55 + Math.random() * 25).toFixed(1),
    moisture_pct: +(t.moisture_pct * factor * (0.85 + Math.random() * 0.3)).toFixed(2),
  };
  if (t.ochratoxin_A_ppb) payload.ochratoxin_A_ppb = +(t.ochratoxin_A_ppb * factor * (0.8 + Math.random() * 0.4)).toFixed(2);
  if (t.aflatoxin_B1_ppb) payload.aflatoxin_B1_ppb = +(t.aflatoxin_B1_ppb * factor * (0.8 + Math.random() * 0.4)).toFixed(2);
  payload.pesticide_residues_ppb = +((5 + Math.random() * 35) * factor).toFixed(2);
  payload.pesticide_residues_ok = (payload.pesticide_residues_ppb as number) <= 30;
  return payload;
}

function RiskGauge({ level, score }: { level: string; score: number }) {
  const meta = RISK_COLORS[level] ?? RISK_COLORS.safe;
  const r = 40;
  const c = 2 * Math.PI * r;
  const filled = c * (Math.min(score, 5) / 5);
  return (
    <div className="relative flex h-28 w-28 items-center justify-center">
      <svg viewBox="0 0 100 100" className="h-28 w-28 -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="#e2e8f0" strokeWidth="9" />
        <circle cx="50" cy="50" r={r} fill="none" stroke={meta.ring} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${filled} ${c}`} />
      </svg>
      <div className="absolute text-center">
        <p className={`text-sm font-bold ${meta.text}`}>{meta.label}</p>
        <p className="text-xs text-slate-400">{score.toFixed(1)}/5</p>
      </div>
    </div>
  );
}

export default function BiosensorPage() {
  useRequireAuth();
  const readings = useApi<Reading[]>("/biosensor/readings?limit=30");
  const [crop, setCrop] = useState("coffee");
  const [contamination, setContamination] = useState<"low" | "moderate" | "severe">("low");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function simulate() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/biosensor/readings", {
        body: {
          device_id: `sensor-${Math.random().toString(16).slice(2, 6)}`,
          crop_name: crop,
          batch_id: `batch-${Date.now().toString(36)}`,
          payload: generateMockPayload(crop, contamination),
        },
      });
      readings.refetch();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const latest = readings.data?.[0];

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Biosensor tracking</h1>
        <p className="text-sm text-slate-500">
          Multi-threat monitoring — mycotoxins, pesticide residues, moisture. Phase 1 uses simulated device data.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="activity" className="h-4 w-4 text-brand-600" /> Simulate device reading
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Crop</span>
            <select value={crop} onChange={(e) => setCrop(e.target.value)}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200">
              <option value="coffee">Coffee</option>
              <option value="maize">Maize</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Contamination</span>
            <select value={contamination} onChange={(e) => setContamination(e.target.value as "low" | "moderate" | "severe")}
              className="rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200">
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="severe">Severe</option>
            </select>
          </label>
          <button onClick={simulate} disabled={busy}
            className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
            {busy ? "Sending…" : "Send reading"}
          </button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </div>
      </div>

      {latest && (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-slate-900">Latest reading</h2>
              <p className="text-xs text-slate-500">
                {latest.device_id} · {latest.crop_name} · {latest.batch_id} · {timeAgo(latest.received_at)}
              </p>
            </div>
            <StatusBadge status={latest.threat_level} />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-6">
            <RiskGauge level={latest.threat_level} score={latest.risk_score} />
            <div className="grid flex-1 gap-3 sm:grid-cols-2">
              {Object.entries(latest.payload).map(([key, value]) => (
                <div key={key} className="rounded-xl bg-slate-50 px-3 py-2">
                  <p className="text-xs text-slate-500">{key.replace(/_/g, " ")}</p>
                  <p className="text-sm font-bold text-slate-900">{String(value)}</p>
                </div>
              ))}
            </div>
          </div>
          {latest.threats.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-slate-100 pt-4">
              {latest.threats.map((t) => (
                <div key={t.code} className="flex items-start justify-between gap-3 rounded-xl bg-red-50 px-3 py-2 text-sm">
                  <div>
                    <p className="font-semibold capitalize text-red-800">{t.label.replace(/_/g, " ")}</p>
                    <p className="text-xs text-red-700">{t.message}</p>
                  </div>
                  <span className="shrink-0 font-bold text-red-700">
                    {t.value} / limit {t.limit}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 font-semibold text-slate-900">Reading history</h2>
        {readings.loading ? (
          <Spinner />
        ) : readings.data?.length ? (
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs text-slate-500">
                <tr>
                  <th className="px-4 py-2.5">Device</th>
                  <th className="px-4 py-2.5">Crop</th>
                  <th className="px-4 py-2.5">Batch</th>
                  <th className="px-4 py-2.5">Risk</th>
                  <th className="px-4 py-2.5">Received</th>
                </tr>
              </thead>
              <tbody>
                {readings.data.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium text-slate-800">{r.device_id}</td>
                    <td className="px-4 py-2.5 capitalize text-slate-600">{r.crop_name}</td>
                    <td className="px-4 py-2.5 text-slate-500">{r.batch_id ?? "—"}</td>
                    <td className="px-4 py-2.5"><StatusBadge status={r.threat_level} /></td>
                    <td className="px-4 py-2.5 text-slate-500">{formatDateTime(r.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center text-sm text-slate-500">
            No readings yet — generate one above to test the pipeline.
          </p>
        )}
      </section>
    </div>
  );
}
