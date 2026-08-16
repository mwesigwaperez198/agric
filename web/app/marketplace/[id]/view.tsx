"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { Listing } from "@/components/ListingCard";
import { Spinner } from "@/components/ui";
import { useAuthStore } from "@/stores/auth-store";
import { formatMoney, formatDateTime, getErrorMessage } from "@/lib/utils";
import { Icons } from "@/components/icons";

export default function ListingDetailView() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  const [listing, setListing] = useState<Listing | null>(null);
  const [loading, setLoading] = useState(true);
  const [qty, setQty] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiFetch<Listing>(`/listings/${params.id}`, { auth: false })
      .then(setListing)
      .catch(() => setListing(null))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <Spinner />;
  if (!listing) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-xl font-bold text-slate-700">Listing not found</h1>
        <Link href="/marketplace" className="mt-2 inline-block text-brand-600 hover:underline">
          Back to marketplace
        </Link>
      </div>
    );
  }

  const isOwn = user?.id === listing.seller_id;
  const total = qty * listing.price_per_unit;

  async function buy() {
    if (!user) {
      router.push("/login");
      return;
    }
    if (!listing) return;
    setBusy(true);
    setError(null);
    try {
      const order = await apiFetch<{ id: number }>("/orders", { body: { listing_id: listing.id, quantity: qty } });
      router.push(`/orders/${order.id}`);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-fade-in grid gap-6 lg:grid-cols-2">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex h-72 items-center justify-center bg-gradient-to-br from-emerald-50 to-amber-50">
          {listing.images[0] ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={listing.images[0]} alt={listing.crop_name} className="h-full w-full object-cover" />
          ) : (
            <Icons name="leaf" className="h-16 w-16 text-brand-500" />
          )}
        </div>
        <div className="p-6">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold capitalize text-slate-600">
              {listing.category}
            </span>
            <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
              Grade: {listing.quality_grade ?? "Unspecified"}
            </span>
            {listing.distance_km != null && (
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                {listing.distance_km.toFixed(1)} km away
              </span>
            )}
          </div>
          <h1 className="mt-3 text-2xl font-bold text-slate-900">{listing.crop_name}</h1>
          {listing.variety && <p className="text-sm text-slate-500">{listing.variety}</p>}
          <p className="mt-3 text-slate-600">{listing.description ?? "No description provided."}</p>
          <div className="mt-4 space-y-1 border-t border-slate-100 pt-4 text-sm text-slate-600">
            <p><strong className="text-slate-800">Seller:</strong> {listing.seller_name ?? `#${listing.seller_id}`}</p>
            {listing.farm_name && <p><strong className="text-slate-800">Farm:</strong> {listing.farm_name}</p>}
            {listing.region && <p><strong className="text-slate-800">Region:</strong> {listing.region}</p>}
            {listing.harvest_date && <p><strong className="text-slate-800">Harvest:</strong> {listing.harvest_date}</p>}
            <p className="text-xs text-slate-400">Listed {formatDateTime(listing.created_at)}</p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <p className="text-sm text-slate-500">Price per {listing.unit}</p>
          <p className="text-3xl font-bold text-slate-900">{formatMoney(listing.price_per_unit, listing.currency)}</p>

          {isOwn ? (
            <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2.5 text-sm text-slate-600">
              This is your listing. View it in your dashboard.
            </p>
          ) : (
            <>
              <label className="mt-5 block">
                <span className="mb-1 block text-sm font-medium text-slate-700">
                  Quantity ({Math.max(0, listing.quantity)} {listing.unit} available)
                </span>
                <input
                  type="number"
                  min={1}
                  max={listing.quantity}
                  value={qty}
                  onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                />
              </label>

              <div className="mt-4 space-y-2 border-t border-slate-100 pt-4 text-sm">
                <div className="flex justify-between text-slate-600">
                  <span>Subtotal</span>
                  <span className="font-semibold text-slate-900">{formatMoney(total, listing.currency)}</span>
                </div>
                <div className="flex justify-between text-slate-600">
                  <span>Escrow protection</span>
                  <span className="font-semibold text-emerald-600">
                    <Icons name="shield" className="mr-1 inline h-4 w-4" />Included
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-100 pt-2 text-base font-bold text-slate-900">
                  <span>Total</span>
                  <span>{formatMoney(total, listing.currency)}</span>
                </div>
              </div>

              {error && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

              <button
                onClick={buy}
                disabled={busy || listing.status !== "active" || qty > listing.quantity}
                className="mt-4 w-full rounded-xl bg-brand-500 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
              >
                {listing.status !== "active"
                  ? `Unavailable (${listing.status.replace("_", " ")})`
                  : busy
                    ? "Placing order…"
                    : "Buy now · pay on delivery"}
              </button>
              <p className="mt-2 text-center text-xs text-slate-400">
                Funds are held in escrow and only released to the farmer after you confirm delivery.
              </p>
            </>
          )}
        </div>

        <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 text-sm text-brand-800">
          <div className="flex items-center gap-2 font-semibold">
            <Icons name="truck" className="h-4 w-4" /> Farm-to-fork assurance
          </div>
          <p className="mt-1 text-brand-700">
            Direct from producer, quality-graded, and covered by a transparent 2.5% platform commission.
          </p>
        </div>
      </div>
    </div>
  );
}
