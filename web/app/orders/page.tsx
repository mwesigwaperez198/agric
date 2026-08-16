"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { StatusBadge, Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney, formatDateTime } from "@/lib/utils";

interface Order {
  id: number;
  buyer_id: number;
  listing_id: number;
  quantity: number;
  unit_price: number;
  total: number;
  currency: string;
  commission_amount: number;
  status: string;
  created_at: string;
}

export default function OrdersPage() {
  useRequireAuth();
  const orders = useApi<Order[]>("/orders");

  return (
    <div className="animate-fade-in">
      <h1 className="text-2xl font-bold text-slate-900">Orders</h1>
      <p className="text-sm text-slate-500">All your purchases and sales, with escrow status.</p>

      <div className="mt-5">
        {orders.loading ? (
          <Spinner />
        ) : orders.data?.length ? (
          <div className="space-y-3">
            {orders.data.map((o) => (
              <Link key={o.id} href={`/orders/${o.id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-colors hover:border-brand-400">
                <div className="flex items-center gap-3">
                  <div className="rounded-xl bg-brand-50 p-2.5 text-brand-600">
                    <Icons name="truck" className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">Order #{o.id}</p>
                    <p className="text-xs text-slate-500">
                      {o.quantity} units @ {formatMoney(o.unit_price, o.currency)} · {formatDateTime(o.created_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-sm font-bold text-slate-900">{formatMoney(o.total, o.currency)}</p>
                  <StatusBadge status={o.status} />
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-14 text-center">
            <Icons name="store" className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-3 font-semibold text-slate-700">No orders yet</p>
            <Link href="/marketplace" className="mt-1 inline-block text-sm font-semibold text-brand-600 hover:underline">
              Browse the marketplace
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
