"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/api";
import { ListingCard, type Listing } from "@/components/ListingCard";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { useAuthStore } from "@/stores/auth-store";

const CATEGORIES = ["", "coffee", "grains", "produce", "livestock", "other"];
const SORTS = [
  { value: "recent", label: "Most recent" },
  { value: "price_asc", label: "Price: low to high" },
  { value: "price_desc", label: "Price: high to low" },
  { value: "nearest", label: "Nearest first" },
];

export default function MarketplacePage() {
  const user = useAuthStore((s) => s.user);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [filters, setFilters] = useState({ q: "", category: "", region: "", sort: "recent", maxDistance: "" });

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.q) params.set("q", filters.q);
      if (filters.category) params.set("category", filters.category);
      if (filters.region) params.set("region", filters.region);
      if (filters.sort) params.set("sort", filters.sort);
      if (filters.maxDistance) params.set("max_distance_km", filters.maxDistance);
      if (coords) {
        params.set("lat", String(coords.lat));
        params.set("lon", String(coords.lon));
      }
      const data = await apiFetch<Listing[]>(`/listings?${params.toString()}`, { auth: false });
      setListings(data);
    } catch {
      setListings([]);
    } finally {
      setLoading(false);
    }
  }, [filters, coords]);

  useEffect(() => {
    fetchListings();
  }, [fetchListings]);

  useEffect(() => {
    if ("geolocation" in navigator && coords === null) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => {},
        { timeout: 4000, maximumAge: 600000 }
      );
    }
  }, [coords]);

  const regionOptions = useMemo(
    () => Array.from(new Set(listings.map((l) => l.region).filter((r): r is string => Boolean(r)))),
    [listings]
  );

  const inputCls =
    "rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="animate-fade-in space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Marketplace</h1>
          <p className="text-sm text-slate-500">
            {user ? `Buying as ${user.full_name.split(" ")[0]}` : "Browse fresh produce from local farmers"}
            {coords && " · sorted by your location"}
          </p>
        </div>
        {user?.role === "farmer" && (
          <a
            href="/dashboard/farmer#new-listing"
            className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600"
          >
            + New listing
          </a>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="relative min-w-0 flex-1">
          <Icons name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
            placeholder="Search coffee, maize, vanilla…"
            className={`${inputCls} w-full pl-9`}
          />
        </div>
        <select value={filters.category} onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))} className={inputCls}>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{c === "" ? "All categories" : c}</option>
          ))}
        </select>
        <select value={filters.region} onChange={(e) => setFilters((f) => ({ ...f, region: e.target.value }))} className={inputCls}>
          <option value="">All regions</option>
          {regionOptions.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <select value={filters.sort} onChange={(e) => setFilters((f) => ({ ...f, sort: e.target.value }))} className={inputCls}>
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <Spinner />
      ) : listings.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-16 text-center">
          <Icons name="store" className="mx-auto h-8 w-8 text-slate-300" />
          <h3 className="mt-3 font-semibold text-slate-700">No listings found</h3>
          <p className="mt-1 text-sm text-slate-500">Try a different search or category.</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {listings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      )}
    </div>
  );
}
