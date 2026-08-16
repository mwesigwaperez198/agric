"use client";

import Link from "next/link";
import { useRequireRole } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { API_URL } from "@/lib/utils";

interface Listing {
  id: number;
  crop_name: string;
  variety?: string;
  description?: string;
  quantity: number;
  unit: string;
  price_per_unit: number;
  category?: string;
  region?: string;
  seller_name?: string;
  farm_name?: string;
  images?: string[];
}

interface Farm {
  id: number;
  name: string;
  region: string;
  description?: string;
}

function resolveImage(src?: string): string {
  if (!src) return "";
  if (src.startsWith("http")) return src;
  return `${API_URL.replace("/api/v1", "")}${src}`;
}

export default function ConsumerDashboard() {
  useRequireRole(["consumer", "admin"]);
  const user = useAuthStore((s) => s.user);
  const listings = useApi<Listing[]>("/listings?status=active&sort=recent");
  const farms = useApi<Farm[]>("/farms/all");

  const featured = listings.data?.slice(0, 6) ?? [];
  const categories = [...new Set(listings.data?.map((l) => l.category).filter(Boolean) ?? [])];

  return (
    <div className="animate-fade-in space-y-6">
      {/* Welcome */}
      <div className="rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 p-6 text-white shadow-lg shadow-brand-600/20">
        <h1 className="text-2xl font-bold">Welcome, {user?.full_name?.split(" ")[0]}</h1>
        <p className="mt-1 text-sm text-white/80">Find fresh, farm-direct produce from local farmers.</p>
        <Link
          href="/marketplace"
          className="mt-4 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-brand-700 shadow-sm hover:bg-white/90"
        >
          <Icons name="search" className="h-4 w-4" /> Browse marketplace
        </Link>
      </div>

      {/* Categories */}
      {categories.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {categories.map((cat) => (
            <Link
              key={cat}
              href={`/marketplace?category=${cat}`}
              className="flex-shrink-0 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:border-brand-300 hover:text-brand-700"
            >
              {cat}
            </Link>
          ))}
        </div>
      )}

      {/* Featured listings */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Available now</h2>
          <Link href="/marketplace" className="text-sm font-semibold text-brand-600 hover:underline">View all</Link>
        </div>
        {listings.loading ? (
          <Spinner />
        ) : featured.length ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {featured.map((item) => (
              <Link
                key={item.id}
                href={`/marketplace/${item.id}`}
                className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-all hover:shadow-md hover:border-brand-300"
              >
                {item.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={resolveImage(item.images[0])}
                    alt={item.crop_name}
                    className="h-32 w-full object-cover"
                  />
                ) : (
                  <div className="flex h-32 w-full items-center justify-center bg-slate-100">
                    <Icons name="leaf" className="h-8 w-8 text-slate-300" />
                  </div>
                )}
                <div className="p-3">
                  <p className="font-semibold capitalize text-slate-900 group-hover:text-brand-700">{item.crop_name}</p>
                  {item.variety && <p className="text-xs text-slate-500">{item.variety}</p>}
                  <div className="mt-2 flex items-center justify-between">
                    <p className="text-sm font-bold text-brand-700">{formatMoney(item.price_per_unit)}<span className="text-xs font-normal text-slate-400">/{item.unit}</span></p>
                    {item.region && <p className="text-xs text-slate-400">{item.region}</p>}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
            <Icons name="store" className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-3 font-semibold text-slate-700">No listings yet</p>
            <p className="text-sm text-slate-500">Farmers are setting up their shops.</p>
          </div>
        )}
      </section>

      {/* Farms */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">Local farms</h2>
          <Link href="/dashboard/farms" className="text-sm font-semibold text-brand-600 hover:underline">View all</Link>
        </div>
        {farms.loading ? (
          <Spinner />
        ) : farms.data && farms.data.length > 0 ? (
          <div className="space-y-2">
            {farms.data.slice(0, 4).map((farm) => (
              <Link
                key={farm.id}
                href="/dashboard/farms"
                className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:shadow-md hover:border-brand-300"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                  <Icons name="leaf" className="h-5 w-5" />
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-slate-900">{farm.name}</p>
                  <p className="text-xs text-slate-500">{farm.region}{farm.description ? ` · ${farm.description}` : ""}</p>
                </div>
                <Icons name="chevron" className="h-4 w-4 text-slate-300" />
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-8 text-center">
            <Icons name="leaf" className="mx-auto h-6 w-6 text-slate-300" />
            <p className="mt-2 text-sm font-semibold text-slate-700">No farms nearby</p>
          </div>
        )}
      </section>

      {/* Quick links */}
      <div className="grid grid-cols-2 gap-3">
        <Link href="/diagnostics" className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <Icons name="scan" className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">AI Assistant</p>
            <p className="text-xs text-slate-500">Ask about farming</p>
          </div>
        </Link>
        <Link href="/insights" className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
            <Icons name="trend" className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Insights</p>
            <p className="text-xs text-slate-500">Market trends</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
