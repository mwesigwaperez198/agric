"use client";

import { useState } from "react";
import { useRequireRole } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { apiFetch } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatDateTime, getErrorMessage } from "@/lib/utils";

interface Farm {
  id: number;
  name: string;
  description: string | null;
  region: string;
  country: string;
  latitude: number | null;
  longitude: number | null;
  certifications: string | null;
  created_at: string;
}

const UGANDA_REGIONS = [
  "Bugisu", "Busoga", "Bunyoro", "Ankole", "Kigezi", "Toro",
  "West Nile", "Acholi", "Lango", "Karamoja", "Sebei", "Bukedi",
  "Mbarara", "Mpigi", "Wakiso", "Mukono", "Jinja", "Mbale",
  "Kasese", "Kabale", "Hoima", "Fort Portal", "Gulu", "Lira",
  "Soroti", "Kampala", "Entebbe", "Masaka", "Mityana", "Luwero",
];

export default function FarmsPage() {
  useRequireRole(["farmer", "admin"]);

  const farms = useApi<Farm[]>("/farms");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    description: "",
    region: "",
    country: "UG",
    latitude: "",
    longitude: "",
    certifications: "",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function createFarm(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setCreating(true);
    try {
      const payload = {
        name: form.name,
        description: form.description || null,
        region: form.region,
        country: form.country,
        latitude: form.latitude ? parseFloat(form.latitude) : null,
        longitude: form.longitude ? parseFloat(form.longitude) : null,
        certifications: form.certifications || null,
      };
      await apiFetch<Farm>("/farms", { method: "POST", body: payload });
      setForm({ name: "", description: "", region: "", country: "UG", latitude: "", longitude: "", certifications: "" });
      setShowForm(false);
      farms.refetch();
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Farms</h1>
          <p className="text-sm text-slate-500">Manage your farm profiles. Each farm can have its own listings.</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
        >
          <Icons name="plus" className="h-4 w-4" />
          {showForm ? "Cancel" : "Add farm"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={createFarm} className="animate-fade-in space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="store" className="h-4 w-4 text-brand-600" /> Register a new farm
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Farm name *</span>
              <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className={inputCls} placeholder="e.g. Mwesigwa Coffee Farm" />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Region *</span>
              <select required value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} className={inputCls}>
                <option value="">Select region</option>
                {UGANDA_REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Description</span>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3}
              className={inputCls} placeholder="Describe your farm — size, crops grown, practices, etc." />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Latitude (optional)</span>
              <input type="number" step="any" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })}
                className={inputCls} placeholder="-1.9403" />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Longitude (optional)</span>
              <input type="number" step="any" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })}
                className={inputCls} placeholder="29.8739" />
            </label>
          </div>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Certifications (optional)</span>
            <input value={form.certifications} onChange={(e) => setForm({ ...form, certifications: e.target.value })}
              className={inputCls} placeholder="e.g. Organic, Fair Trade, Rainforest Alliance" />
          </label>
          {formError && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</p>}
          <button type="submit" disabled={creating}
            className="w-full rounded-xl bg-brand-500 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
            {creating ? "Creating…" : "Register farm"}
          </button>
        </form>
      )}

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-4 flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="store" className="h-4 w-4 text-brand-600" /> Registered farms
        </h2>
        {farms.loading ? (
          <Spinner />
        ) : farms.data?.length ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {farms.data.map((farm) => (
              <div key={farm.id} className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-slate-900">{farm.name}</p>
                    <p className="text-sm text-slate-500">{farm.region}, {farm.country}</p>
                  </div>
                  <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">#{farm.id}</span>
                </div>
                {farm.description && (
                  <p className="mt-2 text-sm text-slate-600 line-clamp-2">{farm.description}</p>
                )}
                {farm.certifications && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {farm.certifications.split(",").map((cert) => (
                      <span key={cert.trim()} className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                        {cert.trim()}
                      </span>
                    ))}
                  </div>
                )}
                {farm.latitude && farm.longitude && (
                  <p className="mt-2 text-xs text-slate-400">
                    {farm.latitude.toFixed(4)}, {farm.longitude.toFixed(4)}
                  </p>
                )}
                <p className="mt-2 text-xs text-slate-400">Created {formatDateTime(farm.created_at)}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center">
            <Icons name="store" className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 text-sm text-slate-500">No farms registered yet.</p>
            <p className="text-xs text-slate-400">Add your first farm to start creating listings.</p>
          </div>
        )}
      </div>
    </div>
  );
}
