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
  reasons: string[];
  recommended: boolean;
}

interface Insights {
  top_trends: Array<{ crop_name: string; region: string; trend: string; current_price: number; expected_change_pct: number }>;
  recommendations: Recommendation[];
}

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

export default function InsightsPage() {
  useRequireAuth();
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(true);
  const [crop, setCrop] = useState("coffee");
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);

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

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Market insights</h1>
        <p className="text-sm text-slate-500">
          Price forecasting and weather-driven crop recommendations for better decisions.
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
              {["coffee", "maize", "vanilla"].map((c) => (
                <option key={c} value={c}>{c[0].toUpperCase() + c.slice(1)}</option>
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
              No price history for {crop}. Run the seed script or record prices to enable forecasting.
            </p>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="spark" className="h-4 w-4 text-brand-600" /> Crop recommendations
          </h2>
          {loading ? (
            <Spinner />
          ) : insights?.recommendations.length ? (
            <div className="space-y-3">
              {insights.recommendations.map((rec) => (
                <div key={rec.crop_name} className="flex items-start justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5">
                  <div>
                    <p className="flex items-center gap-2 font-semibold capitalize text-slate-800">
                      {rec.crop_name}
                      {rec.recommended && (
                        <span className="rounded-full bg-brand-100 px-2 py-0.5 text-[10px] font-bold text-brand-700">RECOMMENDED</span>
                      )}
                    </p>
                    <p className="text-xs text-slate-500">{rec.reasons[0]}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-brand-600">{rec.score}/10</p>
                    <p className="text-[11px] capitalize text-slate-400">{rec.confidence}</p>
                  </div>
                </div>
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
                  <p className="font-semibold capitalize text-slate-800">{t.crop_name}</p>
                  <span className={`text-xs font-bold ${trendColor(t.trend)}`}>
                    {t.trend === "up" ? "▲" : t.trend === "down" ? "▼" : "▬"} {t.trend}
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
