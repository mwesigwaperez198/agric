"use client";

import Link from "next/link";
import { useRequireRole } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { StatusBadge, Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

interface Order {
  id: number;
  buyer_id: number;
  listing_id: number;
  quantity: number;
  total: number;
  currency: string;
  commission_amount: number;
  status: string;
  created_at: string;
}

interface Wallet {
  balance: number;
  currency: string;
}

export default function ConsumerDashboard() {
  useRequireRole(["consumer", "admin"]);
  const user = useAuthStore((s) => s.user);
  const orders = useApi<Order[]>("/orders");
  const wallet = useApi<Wallet>("/me/wallet");

  const mine = orders.data?.filter((o) => o.buyer_id === user?.id) ?? [];
  const open = mine.filter((o) => ["in_escrow", "pending", "shipped"].includes(o.status));

  return (
    <div className="animate-fade-in space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Consumer dashboard</h1>
          <p className="text-sm text-slate-500">Track your farm-fresh purchases, {user?.full_name?.split(" ")[0]}.</p>
        </div>
        <Link href="/marketplace" className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600">
          Shop produce
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Open orders</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{open.length}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Total spent</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {formatMoney(mine.reduce((s, o) => s + o.total, 0), "UGX")}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm text-slate-500">Wallet balance</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">
            {wallet.data ? formatMoney(wallet.data.balance, wallet.data.currency) : "—"}
          </p>
        </div>
      </div>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="truck" className="h-4 w-4 text-brand-600" /> My orders
          </h2>
          <Link href="/orders" className="text-sm font-semibold text-brand-600 hover:underline">View all</Link>
        </div>
        {orders.loading ? (
          <Spinner />
        ) : mine.length ? (
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
            {mine.slice(0, 6).map((o) => (
              <Link key={o.id} href={`/orders/${o.id}`} className="flex items-center justify-between border-b border-slate-100 px-4 py-3 text-sm last:border-0 hover:bg-slate-50">
                <div>
                  <p className="font-semibold text-slate-800">Order #{o.id} · {o.quantity} units</p>
                  <p className="text-xs text-slate-500">
                    {formatMoney(o.total, o.currency)} · commission {formatMoney(o.commission_amount, o.currency)}
                  </p>
                </div>
                <StatusBadge status={o.status} />
              </Link>
            ))}
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-12 text-center">
            <Icons name="store" className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-3 font-semibold text-slate-700">No orders yet</p>
            <Link href="/marketplace" className="mt-1 inline-block text-sm font-semibold text-brand-600 hover:underline">
              Explore the marketplace
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
