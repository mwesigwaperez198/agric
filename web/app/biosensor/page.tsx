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

const CROP_LIST = [
  { value: "coffee", label: "Coffee", type: "Perennial" },
  { value: "maize", label: "Maize", type: "Annual" },
  { value: "beans", label: "Beans", type: "Annual" },
  { value: "groundnuts", label: "Groundnuts", type: "Annual" },
  { value: "soybean", label: "Soybean", type: "Annual" },
  { value: "cassava", label: "Cassava", type: "Root" },
  { value: "banana", label: "Banana", type: "Fruit" },
  { value: "vanilla", label: "Vanilla", type: "Spice" },
  { value: "cocoa", label: "Cocoa", type: "Tree" },
  { value: "tea", label: "Tea", type: "Perennial" },
  { value: "rice", label: "Rice", type: "Annual" },
  { value: "millet", label: "Millet", type: "Annual" },
  { value: "sorghum", label: "Sorghum", type: "Annual" },
  { value: "sesame", label: "Sesame", type: "Annual" },
  { value: "sunflower", label: "Sunflower", type: "Annual" },
  { value: "wheat", label: "Wheat", type: "Annual" },
  { value: "sweet_potato", label: "Sweet Potato", type: "Root" },
  { value: "irish_potato", label: "Irish Potato", type: "Root" },
  { value: "tomato", label: "Tomato", type: "Vegetable" },
  { value: "onion", label: "Onion", type: "Vegetable" },
  { value: "chilli", label: "Chilli", type: "Vegetable" },
  { value: "cabbage", label: "Cabbage", type: "Vegetable" },
  { value: "avocado", label: "Avocado", type: "Tree" },
  { value: "mango", label: "Mango", type: "Tree" },
  { value: "pineapple", label: "Pineapple", type: "Fruit" },
  { value: "papaya", label: "Papaya", type: "Tree" },
  { value: "passion_fruit", label: "Passion Fruit", type: "Fruit" },
  { value: "watermelon", label: "Watermelon", type: "Vegetable" },
  { value: "pumpkin", label: "Pumpkin", type: "Vegetable" },
  { value: "okra", label: "Okra", type: "Vegetable" },
  { value: "eggplant", label: "Eggplant", type: "Vegetable" },
  { value: "sugarcane", label: "Sugarcane", type: "Perennial" },
  { value: "cotton", label: "Cotton", type: "Annual" },
  { value: "macadamia", label: "Macadamia", type: "Tree" },
  { value: "cashew", label: "Cashew", type: "Tree" },
  { value: "ginger", label: "Ginger", type: "Spice" },
  { value: "turmeric", label: "Turmeric", type: "Spice" },
];

const CROP_LIMITS: Record<string, Record<string, number>> = {
  coffee: { ochratoxin_A_ppb: 2.0, moisture_pct: 12.5 },
  maize: { aflatoxin_B1_ppb: 10.0, moisture_pct: 13.5 },
  beans: { aflatoxin_B1_ppb: 10.0, moisture_pct: 14.0 },
  groundnuts: { aflatoxin_B1_ppb: 10.0, moisture_pct: 10.0 },
  soybean: { aflatoxin_B1_ppb: 20.0, moisture_pct: 13.0 },
  cassava: { hydrogen_cyanide_ppm: 50.0, moisture_pct: 14.0 },
  banana: { soil_ph: 6.0, moisture_pct: 15.0 },
  vanilla: { moisture_pct: 25.0 },
  cocoa: { ochratoxin_A_ppb: 2.0, moisture_pct: 7.5 },
  tea: { moisture_pct: 10.0, pesticide_residues_ppb: 30.0 },
  rice: { arsenic_ppm: 0.3, moisture_pct: 14.0 },
  millet: { aflatoxin_B1_ppb: 10.0, moisture_pct: 12.0 },
  sorghum: { aflatoxin_B1_ppb: 10.0, moisture_pct: 13.0 },
  sesame: { aflatoxin_B1_ppb: 10.0, moisture_pct: 9.0 },
  sunflower: { aflatoxin_B1_ppb: 10.0, moisture_pct: 10.0 },
  wheat: { moisture_pct: 13.0, moisture_loss_pct: 0.5 },
  tomato: { soil_ph: 6.2, moisture_pct: 90.0 },
  onion: { soil_ph: 6.5, moisture_pct: 6.0 },
  avocado: { soil_ph: 6.0, moisture_pct: 65.0 },
  mango: { soil_ph: 5.5, moisture_pct: 80.0 },
  pineapple: { soil_ph: 5.0, moisture_pct: 85.0 },
  sugarcane: { soil_ph: 6.0, moisture_pct: 70.0 },
  cotton: { moisture_pct: 8.0, moisture_loss_pct: 0.5 },
  macadamia: { moisture_pct: 3.5, moisture_loss_pct: 0.3 },
  cashew: { aflatoxin_B1_ppb: 10.0, moisture_pct: 10.0 },
  ginger: { moisture_pct: 60.0, soil_ph: 5.8 },
  turmeric: { moisture_pct: 50.0, soil_ph: 5.5 },
};

const CROP_GUIDANCE: Record<string, Record<string, string>> = {
  coffee: {
    drying: "Sun-dry on raised beds to 12% moisture. Turn beans every 2 hours.",
    storage: "Store in clean jute bags on pallets. Temperature below 25C.",
    mycotoxin: "Ochratoxin A forms during improper fermentation. Ferment 48-72hrs.",
    general: "Use certified seedlings (Ruiru 11, NARO 1). Apply 200g NPK per tree twice yearly.",
  },
  maize: {
    drying: "Dry to 13% moisture within 24 hours. Use hermetic bags (PICS) for storage.",
    mycotoxin: "Aflatoxin B1 is produced by Aspergillus. Dry fast and store dry.",
    general: "Plant hybrid varieties (KH 600-23A, Longe 5). Space 75cm x 25cm.",
  },
  beans: {
    drying: "Sun-dry to 12-13% moisture on tarpaulins. Turn regularly.",
    mycotoxin: "Aflatoxin risk exists. Ensure proper drying before storage.",
    general: "Inoculate with Rhizobium. Rotate with cereals.",
  },
  groundnuts: {
    drying: "Dry in pods to 10% moisture. Shell only when fully dry.",
    mycotoxin: "HIGH RISK for aflatoxin. Dry immediately after harvest.",
    general: "Plant early (May-June). Inoculate with rhizobium.",
  },
  cassava: {
    drying: "Peel and chip within 24 hours. Dry chips to 13% moisture.",
    mycotoxin: "HCN (cyanide) is the primary concern. Process properly.",
    general: "Harvest 8-12 months after planting.",
  },
  banana: {
    general: "Use tissue-culture plantlings. De-sucker to 1 strong follower. Mulch heavily.",
  },
  tomato: {
    general: "Stake plants. Prune suckers. Irrigate consistently. Rotate with legumes.",
  },
};

const RISK_COLORS: Record<string, { ring: string; text: string; label: string }> = {
  safe: { ring: "#10b981", text: "text-emerald-600", label: "SAFE" },
  watch: { ring: "#f59e0b", text: "text-amber-600", label: "WATCH" },
  warning: { ring: "#f97316", text: "text-orange-600", label: "WARNING" },
  critical: { ring: "#ef4444", text: "text-red-600", label: "CRITICAL" },
};

function generateMockPayload(crop: string, contamination: string) {
  const limits = CROP_LIMITS[crop] ?? { moisture_pct: 15.0 };
  const factor = { low: 0.6, moderate: 1.3, severe: 2.4 }[contamination as "low" | "moderate" | "severe"] ?? 0.6;

  const payload: Record<string, number | boolean> = {
    temperature_c: +(22 + (Math.random() - 0.5) * 6).toFixed(1),
    humidity_pct: +(55 + Math.random() * 25).toFixed(1),
    soil_moisture: +(40 + Math.random() * 30).toFixed(1),
    soil_ph: +(5.5 + Math.random() * 2).toFixed(2),
  };

  if (limits.moisture_pct !== undefined) {
    payload.moisture_pct = +(limits.moisture_pct * factor * (0.85 + Math.random() * 0.3)).toFixed(2);
  }
  if (limits.ochratoxin_A_ppb) {
    payload.ochratoxin_A_ppb = +(limits.ochratoxin_A_ppb * factor * (0.8 + Math.random() * 0.4)).toFixed(2);
  }
  if (limits.aflatoxin_B1_ppb) {
    payload.aflatoxin_B1_ppb = +(limits.aflatoxin_B1_ppb * factor * (0.8 + Math.random() * 0.4)).toFixed(2);
  }
  if (limits.arsenic_ppm) {
    payload.arsenic_ppm = +(limits.arsenic_ppm * factor * (0.8 + Math.random() * 0.4)).toFixed(3);
  }
  if (limits.hydrogen_cyanide_ppm) {
    payload.hydrogen_cyanide_ppm = +(limits.hydrogen_cyanide_ppm * factor * (0.8 + Math.random() * 0.4)).toFixed(1);
  }
  if (limits.soil_ph) {
    payload.soil_ph = +(limits.soil_ph * (0.9 + Math.random() * 0.2)).toFixed(2);
  }
  if (limits.moisture_loss_pct) {
    payload.moisture_loss_pct = +(limits.moisture_loss_pct * factor * (0.8 + Math.random() * 0.4)).toFixed(2);
  }

  payload.nitrogen_ppm = +(20 + Math.random() * 40).toFixed(1);
  payload.phosphorus_ppm = +(10 + Math.random() * 30).toFixed(1);
  payload.potassium_ppm = +(100 + Math.random() * 200).toFixed(1);

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
  const [showGuidance, setShowGuidance] = useState(false);

  async function simulate() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/biosensor/readings", {
        method: "POST",
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
  const guidance = CROP_GUIDANCE[crop];
  const selectedCrop = CROP_LIST.find((c) => c.value === crop);

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Biosensor tracking</h1>
        <p className="text-sm text-slate-500">
          Multi-threat monitoring for 30+ crops — mycotoxins, pesticide residues, soil health, moisture.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="activity" className="h-4 w-4 text-brand-600" /> Simulate device reading
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="block min-w-[200px]">
            <span className="mb-1 block text-sm font-medium text-slate-700">Crop</span>
            <select value={crop} onChange={(e) => setCrop(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200">
              {CROP_LIST.map((c) => (
                <option key={c.value} value={c.value}>{c.label} ({c.type})</option>
              ))}
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
        {selectedCrop && (
          <p className="mt-2 text-xs text-slate-400">
            Monitoring: {selectedCrop.label} — ideal temp {selectedCrop.type === "Perennial" || selectedCrop.type === "Tree" ? "18-27C" : "20-28C"}, type: {selectedCrop.type}
          </p>
        )}
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

      {guidance && (
        <section className="rounded-2xl border border-blue-100 bg-blue-50 p-5">
          <button onClick={() => setShowGuidance(!showGuidance)}
            className="flex w-full items-center justify-between text-left">
            <h2 className="flex items-center gap-2 font-semibold text-blue-900">
              <Icons name="shield" className="h-4 w-4" /> {crop.charAt(0).toUpperCase() + crop.slice(1)} handling guidance
            </h2>
            <span className="text-blue-600">{showGuidance ? "▲" : "▼"}</span>
          </button>
          {showGuidance && (
            <div className="mt-3 space-y-2">
              {guidance.drying && (
                <div className="rounded-lg bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-blue-800">Drying</p>
                  <p className="text-sm text-slate-700">{guidance.drying}</p>
                </div>
              )}
              {guidance.storage && (
                <div className="rounded-lg bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-blue-800">Storage</p>
                  <p className="text-sm text-slate-700">{guidance.storage}</p>
                </div>
              )}
              {guidance.mycotoxin && (
                <div className="rounded-lg bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-blue-800">Mycotoxin prevention</p>
                  <p className="text-sm text-slate-700">{guidance.mycotoxin}</p>
                </div>
              )}
              {guidance.general && (
                <div className="rounded-lg bg-white px-3 py-2">
                  <p className="text-xs font-semibold text-blue-800">General tips</p>
                  <p className="text-sm text-slate-700">{guidance.general}</p>
                </div>
              )}
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
