"use client";

import { useState } from "react";
import Link from "next/link";
import { useRequireRole } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { apiFetch } from "@/lib/api";
import type { Listing } from "@/components/ListingCard";
import { StatusBadge, Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney, getErrorMessage } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

interface Farm {
  id: number;
  name: string;
  region: string;
  country: string;
  latitude?: number | null;
  longitude?: number | null;
}

interface Order {
  id: number;
  buyer_id: number;
  seller_id: number;
  listing_id: number;
  quantity: number;
  total: number;
  currency: string;
  status: string;
  created_at: string;
}

interface Wallet {
  balance: number;
  currency: string;
}

export default function FarmerDashboard() {
  useRequireRole(["farmer", "admin"]);
  const user = useAuthStore((s) => s.user);
  const [newListing, setNewListing] = useState({
    crop_name: "",
    category: "coffee",
    variety: "",
    quantity: "",
    unit: "kg",
    price_per_unit: "",
    region: "",
    quality_grade: "",
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const farms = useApi<Farm[]>("/farms");
  const wallet = useApi<Wallet>("/me/wallet");
  const sales = useApi<Order[]>("/orders");

  // Because seller_id is not a personal filter, refetch authenticated orders for the farmer view.
  const myListings = useApi<Listing[]>(`/listings?seller_id=${user?.id ?? 0}`, false);

  async function createListing(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setCreating(true);
    try {
      const payload = {
        ...newListing,
        quantity: Number(newListing.quantity),
        price_per_unit: Number(newListing.price_per_unit),
      };
      await apiFetch<Listing>("/listings", { body: payload });
      setNewListing({ crop_name: "", category: "coffee", variety: "", quantity: "", unit: "kg", price_per_unit: "", region: "", quality_grade: "" });
      myListings.refetch();
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
          <h1 className="text-2xl font-bold text-slate-900">Farmer dashboard</h1>
          <p className="text-sm text-slate-500">Welcome back, {user?.full_name?.split(" ")[0]}</p>
        </div>
        <Link href="/marketplace" className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600">
          Browse marketplace
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Active listings</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{myListings.data?.filter((l) => l.status === "active").length ?? "—"}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Earnings (wallet)</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{wallet.data ? formatMoney(wallet.data.balance, wallet.data.currency) : "—"}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Sales volume</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {sales.data?.filter((o) => o.seller_id === user?.id).length ?? "—"}
          </p>
        </div>
      </div>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="store" className="h-4 w-4 text-brand-600" /> My farms
          </h2>
          {farms.loading ? (
            <Spinner />
          ) : farms.data?.length ? (
            <ul className="space-y-2">
              {farms.data.map((farm) => (
                <li key={farm.id} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2.5">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{farm.name}</p>
                    <p className="text-xs text-slate-500">{farm.region}, {farm.country}</p>
                  </div>
                  <span className="text-xs text-slate-400">#{farm.id}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl bg-amber-50 px-3 py-2.5 text-sm text-amber-700">
              No farm registered yet. Listings auto-attach to your farm once added.
            </p>
          )}
        </div>

        <form id="new-listing" onSubmit={createListing} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="spark" className="h-4 w-4 text-brand-600" /> New listing
          </h2>
          <div className="grid grid-cols-2 gap-3">
            <input required value={newListing.crop_name} onChange={(e) => setNewListing({ ...newListing, crop_name: e.target.value })} className={inputCls} placeholder="Crop name (e.g. Arabica Coffee)" />
            <select value={newListing.category} onChange={(e) => setNewListing({ ...newListing, category: e.target.value })} className={inputCls}>
              <option value="coffee">Coffee</option>
              <option value="grains">Grains</option>
              <option value="produce">Produce</option>
              <option value="livestock">Livestock</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <input value={newListing.variety} onChange={(e) => setNewListing({ ...newListing, variety: e.target.value })} className={inputCls} placeholder="Variety (optional)" />
            <input value={newListing.quality_grade} onChange={(e) => setNewListing({ ...newListing, quality_grade: e.target.value })} className={inputCls} placeholder="Grade (e.g. AA)" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <input required type="number" min={1} value={newListing.quantity} onChange={(e) => setNewListing({ ...newListing, quantity: e.target.value })} className={inputCls} placeholder="Quantity" />
            <select value={newListing.unit} onChange={(e) => setNewListing({ ...newListing, unit: e.target.value })} className={inputCls}>
              <option value="kg">kg</option>
              <option value="t">tonne</option>
              <option value="head">head</option>
              <option value="bunch">bunch</option>
              <option value="sack">sack</option>
            </select>
            <input required type="number" min={1} value={newListing.price_per_unit} onChange={(e) => setNewListing({ ...newListing, price_per_unit: e.target.value })} className={inputCls} placeholder="Price/unit (UGX)" />
          </div>
          <input value={newListing.region} onChange={(e) => setNewListing({ ...newListing, region: e.target.value })} className={inputCls} placeholder="Region (e.g. Mbarara)" />
          {formError && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{formError}</p>}
          <button type="submit" disabled={creating} className="w-full rounded-xl bg-brand-500 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
            {creating ? "Publishing…" : "Publish listing"}
          </button>
        </form>
      </section>

      <section>
        <h2 className="mb-3 font-semibold text-slate-900">My listings</h2>
        {myListings.loading ? (
          <Spinner />
        ) : myListings.data?.length ? (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {myListings.data.map((l) => (
              <div key={l.id} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-semibold text-slate-900">{l.crop_name}</p>
                    <p className="text-xs text-slate-500">{l.variety ?? l.category} · {l.region ?? "—"}</p>
                  </div>
                  <StatusBadge status={l.status} />
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  {formatMoney(l.price_per_unit, l.currency)} / {l.unit}
                  <span className="text-slate-400"> · {l.quantity} {l.unit} left</span>
                </p>
                <Link href={`/marketplace/${l.id}`} className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline">
                  View <Icons name="arrow" className="h-3.5 w-3.5" />
                </Link>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center text-sm text-slate-500">
            No listings yet — publish your first crop above.
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="truck" className="h-4 w-4 text-brand-600" /> Sales & orders
        </h2>
        {sales.loading ? (
          <Spinner />
        ) : sales.data?.filter((o) => o.seller_id === user?.id).length ? (
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {sales.data
              .filter((o) => o.seller_id === user?.id)
              .map((o) => (
                <Link key={o.id} href={`/orders/${o.id}`} className="flex items-center justify-between border-b border-slate-100 px-4 py-3 text-sm last:border-0 hover:bg-slate-50">
                  <div>
                    <p className="font-semibold text-slate-800">Order #{o.id} · {o.quantity} kg</p>
                    <p className="text-xs text-slate-500">{formatMoney(o.total, o.currency)} · {new Date(o.created_at).toLocaleDateString()}</p>
                  </div>
                  <StatusBadge status={o.status} />
                </Link>
              ))}
          </div>
        ) : (
          <p className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-8 text-center text-sm text-slate-500">
            No sales yet. Share your listings with buyers.
          </p>
        )}
      </section>
    </div>
  );
}
