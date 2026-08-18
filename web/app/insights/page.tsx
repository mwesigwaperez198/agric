"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney } from "@/lib/utils";

interface ForecastPoint {
  date: string;
  price: number;
  lower_bound: number;
  upper_bound: number;
}

interface Forecast {
  crop_name: string;
  region: string;
  currency: string;
  current_price: number;
  trend: string;
  forecast: ForecastPoint[];
}

interface Recommendation {
  crop_name: string;
  score: number;
  confidence: string;
  priority: string;
  reasons: string[];
  recommended: boolean;
  type: string;
  season: string;
  ideal_temp: number;
  ideal_rain: number;
  current_price: number | null;
}

interface Insights {
  top_trends: Array<{ crop_name: string; region: string; trend: string; current_price: number; expected_change_pct: number }>;
  recommendations: Recommendation[];
}

interface CropInfo {
  name: string;
  type: string;
  ideal_temp: number;
  ideal_rain: number;
  season: string;
}

const CROP_DISPLAY: Record<string, string> = {
  coffee: "\u2615", maize: "\uD83C\uDF3D", beans: "\uD83C\uDF31", groundnuts: "\uD83C\uDF30",
  soybean: "\uD83C\uDF31", cassava: "\uD83C\uDF38", banana: "\uD83C\uDF4C", vanilla: "\uD83C\uDF3F",
  cocoa: "\uD83C\uDF6B", tea: "\uD83C\uDF75", rice: "\uD83C\uDF5A", millet: "\uD83C\uDF3E",
  sorghum: "\uD83C\uDF3E", sesame: "\uD83C\uDF30", sunflower: "\uD83C\uDF3B", wheat: "\uD83C\uDF3E",
  tomato: "\uD83C\uDF45", onion: "\uD83C\uDF46", avocado: "\uD83E\uDD51", mango: "\uD83C\uDF4D",
  pineapple: "\uD83C\uDF4D", papaya: "\uD83C\uDF4D", tea: "\uD83C\uDF75",
  sugarcane: "\uD83C\uDF3F", cotton: "\u2601\uFE0F", macadamia: "\uD83E\uDD5C", cashew: "\uD83E\uDD5C",
  ginger: "\uD83E\uDDC2", turmeric: "\uD83E\uDDC2", watermelon: "\uD83C\uDF49",
  pumpkin: "\uD83C\uDF83", cabbage: "\uD83C\uDF6F", okra: "\uD83C\uDF31",
  eggplant: "\uD83C\uDF46", capsicum: "\uD83C\uDF36\uFE0F", chilli: "\uD83C\uDF36\uFE0F",
  passion_fruit: "\uD83C\uDF53", jackfruit: "\uD83C\uDF4D", sweet_potato: "\uD83C\uDF60",
  irish_potato: "\uD83C\uDF54", spinach: "\uD83C\uDF3F", lettuce: "\uD83C\uDF3F",
  amaranth: "\uD83C\uDF3F", cucumber: "\uD83C\uDF52", black_pepper: "\uD83C\uDF36\uFE0F",
  cinnamon: "\uD83C\uDF2F\uFE0F", clove: "\uD83C\uDF36\uFE0F", rubber: "\uD83D\uDCA2",
  lentil: "\uD83C\uDF31", chickpea: "\uD83C\uDF31", pigeon_pea: "\uD83C\uDF31",
  cowpea: "\uD83C\uDF31", peanut: "\uD83C\uDF30", tobacco: "\uD83C\uDF3F",
  teff: "\uD83C\uDF3E", lettuce: "\uD83C\uDF3F",
};

function getCropEmoji(name: string): string {
  return CROP_DISPLAY[name] || "\uD83C\uDF3E";
}

const PRIORITY_STYLES: Record<string, { bg: string; border: string; badge: string; label: string }> = {
  high: { bg: "bg-emerald-50", border: "border-emerald-200", badge: "bg-emerald-100 text-emerald-800", label: "HIGH PRIORITY" },
  moderate: { bg: "bg-amber-50", border: "border-amber-200", badge: "bg-amber-100 text-amber-800", label: "MODERATE" },
  low: { bg: "bg-slate-50", border: "border-slate-200", badge: "bg-slate-100 text-slate-600", label: "LOW" },
};

function PriceChart({ forecast }: { forecast: ForecastPoint[] }) {
  const width = 520;
  const height = 180;
  const pad = 12;
  const prices = forecast.map((p) => p.price);
  const min = Math.min(...prices) * 0.97;
  const max = Math.max(...prices) * 1.03;
  const x = (i: number) => pad + (i / Math.max(forecast.length - 1, 1)) * (width - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / (max - min || 1)) * (height - pad * 2);
  const line = forecast.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.price).toFixed(1)}`).join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="7-day price forecast">
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="#cbd5e1" />
      {forecast.map((p, i) => (
        <circle key={p.date} cx={x(i)} cy={y(p.price)} r={3} fill="#059669" />
      ))}
      <path d={line} fill="none" stroke="#10b981" strokeWidth={2} strokeLinejoin="round" />
      <text x={width - pad} y={height - 4} textAnchor="end" fontSize={9} fill="#94a3b8">
        next 7 days
      </text>
    </svg>
  );
}

function RecommendationCard({ rec, isExpanded, onToggle }: { rec: Recommendation; isExpanded: boolean; onToggle: () => void }) {
  const style = PRIORITY_STYLES[rec.priority] ?? PRIORITY_STYLES.low;
  const emoji = getCropEmoji(rec.crop_name);

  return (
    <div className={`rounded-xl border ${style.border} ${style.bg} overflow-hidden transition-all`}>
      <button onClick={onToggle} className="flex w-full items-center justify-between px-4 py-3 text-left">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{emoji}</span>
          <div>
            <p className="flex items-center gap-2 font-semibold capitalize text-slate-800">
              {rec.crop_name.replace(/_/g, " ")}
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${style.badge}`}>
                {style.label}
              </span>
            </p>
            <p className="text-xs text-slate-500">{rec.type} \u00B7 {rec.season}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-lg font-bold text-brand-600">{rec.score}</p>
            <p className="text-[10px] text-slate-400">/10</p>
          </div>
          <span className="text-slate-400">{isExpanded ? "\u25B2" : "\u25BC"}</span>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-slate-100 px-4 py-3 space-y-2">
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded-lg bg-white px-2 py-1.5">
              <p className="text-slate-500">Ideal temp</p>
              <p className="font-bold text-slate-800">{rec.ideal_temp}C</p>
            </div>
            <div className="rounded-lg bg-white px-2 py-1.5">
              <p className="text-slate-500">Ideal rain</p>
              <p className="font-bold text-slate-800">{rec.ideal_rain}mm</p>
            </div>
            <div className="rounded-lg bg-white px-2 py-1.5">
              <p className="text-slate-500">Confidence</p>
              <p className="font-bold capitalize text-slate-800">{rec.confidence}</p>
            </div>
          </div>
          {rec.current_price && (
            <div className="rounded-lg bg-white px-3 py-2 text-sm">
              <span className="text-slate-500">Current price: </span>
              <span className="font-bold text-slate-800">{formatMoney(rec.current_price, "UGX")}</span>
            </div>
          )}
          <div className="space-y-1">
            {rec.reasons.map((reason, i) => (
              <p key={i} className="flex items-start gap-2 text-xs text-slate-600">
                <span className="mt-0.5 text-brand-500">\u2022</span>
                {reason}
              </p>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  useRequireAuth();
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [crop, setCrop] = useState("coffee");
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [expandedRec, setExpandedRec] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "high" | "moderate" | "low">("all");

  useEffect(() => {
    apiFetch<Insights>("/market/insights")
      .then(setInsights)
      .catch(() => setInsights(null))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    setForecastLoading(true);
    apiFetch<Forecast>(`/market/forecast/${crop}`)
      .then(setForecast)
      .catch(() => setForecast(null))
      .finally(() => setForecastLoading(false));
  }, [crop]);

  const trendColor = (t: string) =>
    t === "up" ? "text-emerald-600" : t === "down" ? "text-red-600" : "text-slate-600";

  const filteredRecs = insights?.recommendations.filter((r) => filter === "all" || r.priority === filter) ?? [];
  const highCount = insights?.recommendations.filter((r) => r.priority === "high").length ?? 0;
  const moderateCount = insights?.recommendations.filter((r) => r.priority === "moderate").length ?? 0;
  const lowCount = insights?.recommendations.filter((r) => r.priority === "low").length ?? 0;

  const allCrops = ["coffee", "maize", "beans", "groundnuts", "soybean", "cassava", "banana", "vanilla",
    "cocoa", "tea", "rice", "millet", "sorghum", "sesame", "sunflower", "wheat",
    "tomato", "onion", "avocado", "mango", "pineapple", "sugarcane", "cotton", "macadamia", "cashew"];

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Market insights</h1>
        <p className="text-sm text-slate-500">
          Price forecasting, weather-driven recommendations and crop guidance for 50+ crops.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <Icons name="trend" className="h-4 w-4 text-brand-600" /> 7-day price forecast
            </h2>
            <select value={crop} onChange={(e) => setCrop(e.target.value)}
              className="rounded-xl border border-slate-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200">
              {allCrops.map((c) => (
                <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1).replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>

          {forecastLoading ? (
            <Spinner />
          ) : forecast ? (
            <>
              <div className="mt-4 flex flex-wrap items-center gap-4">
                <div>
                  <p className="text-xs text-slate-500">Current price ({forecast.region})</p>
                  <p className="text-2xl font-bold text-slate-900">{formatMoney(forecast.current_price, forecast.currency)}</p>
                </div>
                <span className={`rounded-full bg-slate-100 px-3 py-1 text-xs font-bold capitalize ${trendColor(forecast.trend)}`}>
                  {forecast.trend === "no_data" ? "No data" : `${forecast.trend} trend`}
                </span>
              </div>
              <PriceChart forecast={forecast.forecast} />
              <div className="grid grid-cols-3 gap-2 border-t border-slate-100 pt-3 text-center text-xs">
                {forecast.forecast.map((p) => (
                  <div key={p.date}>
                    <p className="font-bold text-slate-700">{formatMoney(p.price, forecast.currency)}</p>
                    <p className="text-slate-400">{new Date(p.date).toLocaleDateString("en-UG", { weekday: "short" })}</p>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="mt-4 text-sm text-slate-500">
              No price history for {crop.replace(/_/g, " ")}. Seed price data to enable forecasting.
            </p>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 font-semibold text-slate-900">
              <Icons name="spark" className="h-4 w-4 text-brand-600" /> Crop recommendations
            </h2>
            <div className="flex gap-1">
              {(["all", "high", "moderate", "low"] as const).map((f) => (
                <button key={f} onClick={() => setFilter(f)}
                  className={`rounded-lg px-2 py-1 text-[10px] font-bold transition-colors ${
                    filter === f ? "bg-brand-500 text-white" : "bg-slate-100 text-slate-500 hover:bg-slate-200"
                  }`}>
                  {f === "all" ? "All" : f === "high" ? `High (${highCount})` : f === "moderate" ? `Mod (${moderateCount})` : `Low (${lowCount})`}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <Spinner />
          ) : filteredRecs.length ? (
            <div className="max-h-[500px] space-y-2 overflow-y-auto pr-1">
              {filteredRecs.map((rec) => (
                <RecommendationCard
                  key={rec.crop_name}
                  rec={rec}
                  isExpanded={expandedRec === rec.crop_name}
                  onToggle={() => setExpandedRec(expandedRec === rec.crop_name ? null : rec.crop_name)}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-500">Recommendations appear once weather and price data are available.</p>
          )}
        </section>
      </div>

      {insights?.top_trends.length ? (
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 font-semibold text-slate-900">Trending crops</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {insights.top_trends.map((t) => (
              <div key={`${t.crop_name}-${t.region}`} className="rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <p className="font-semibold capitalize text-slate-800">
                    {getCropEmoji(t.crop_name)} {t.crop_name.replace(/_/g, " ")}
                  </p>
                  <span className={`text-xs font-bold ${trendColor(t.trend)}`}>
                    {t.trend === "up" ? "\u25B2" : t.trend === "down" ? "\u25BC" : "\u25AC"} {t.trend}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {formatMoney(t.current_price, "UGX")}
                  <span className={`ml-2 text-xs font-semibold ${t.expected_change_pct >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                    {t.expected_change_pct >= 0 ? "+" : ""}{t.expected_change_pct}% (7d)
                  </span>
                </p>
                <p className="text-[11px] text-slate-400">{t.region}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
