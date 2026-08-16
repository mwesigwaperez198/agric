"use client";

import Link from "next/link";
import { formatMoney, formatDateTime } from "@/lib/utils";
import { Icons } from "@/components/icons";

export interface Listing {
  id: number;
  farm_id: number;
  seller_id: number;
  crop_name: string;
  category: string;
  variety?: string | null;
  description?: string | null;
  quantity: number;
  unit: string;
  price_per_unit: number;
  currency: string;
  quality_grade?: string | null;
  harvest_date?: string | null;
  region?: string | null;
  status: string;
  created_at: string;
  seller_name?: string | null;
  farm_name?: string | null;
  distance_km?: number | null;
  images: string[];
}

export function ListingCard({ listing, compact = false }: { listing: Listing; compact?: boolean }) {  return (
    <Link
      href={`/marketplace/${listing.id}`}
      className="group flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md"
    >
      <div className="flex h-28 items-center justify-center bg-gradient-to-br from-emerald-50 to-amber-50">
        {listing.images[0] ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={listing.images[0]} alt={listing.crop_name} className="h-full w-full object-cover" />
        ) : (
          <Icons name="leaf" className="h-10 w-10 text-brand-500" />
        )}
      </div>
      <div className="flex flex-1 flex-col gap-1 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold text-slate-900">{listing.crop_name}</h3>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {listing.category}
          </span>
        </div>
        {listing.variety && <p className="text-xs text-slate-500">{listing.variety}</p>}
        <div className="mt-auto flex items-end justify-between pt-2">
          <div>
            <p className="text-base font-bold text-slate-900">{formatMoney(listing.price_per_unit, listing.currency)}</p>
            <p className="text-xs text-slate-500">
              {listing.quantity} {listing.unit}
            </p>
          </div>
          {!compact && listing.distance_km != null && (
            <p className="text-xs font-medium text-brand-600">{listing.distance_km.toFixed(1)} km</p>
          )}
        </div>
        {!compact && (listing.farm_name || listing.seller_name) && (
          <p className="flex items-center gap-1 border-t border-slate-100 pt-2 text-xs text-slate-500">
            <Icons name="store" className="h-3 w-3" />
            {listing.farm_name ?? listing.seller_name}
            {listing.region ? ` · ${listing.region}` : ""}
          </p>
        )}
        {!compact && listing.created_at && (
          <p className="text-[11px] text-slate-400">{formatDateTime(listing.created_at)}</p>
        )}
      </div>
    </Link>
  );
}
