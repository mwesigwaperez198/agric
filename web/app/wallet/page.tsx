"use client";

import Link from "next/link";
import { useRequireAuth } from "@/lib/guards";
import { useApi } from "@/lib/use-api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney } from "@/lib/utils";

interface Wallet {
  balance: number;
  currency: string;
}

interface Order {
  id: number;
  total: number;
  commission_amount: number;
  farmer_net: number;
  status: string;
  created_at: string;
}

export default function WalletPage() {
  useRequireAuth();
  const wallet = useApi<Wallet>("/me/wallet");
  const orders = useApi<Order[]>("/orders");

  const settled = orders.data?.filter((o) => o.status === "settled") ?? [];
  const commissionTotal = settled.reduce((s, o) => s + o.commission_amount, 0);

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Wallet</h1>
        <p className="text-sm text-slate-500">Escrow-protected digital wallet · Mobile Money compatible.</p>
      </div>

      <div className="overflow-hidden rounded-3xl bg-gradient-to-br from-ink-900 to-emerald-950 p-6 text-white shadow-lg">
        <p className="text-sm text-slate-300">Available balance</p>
        <p className="mt-1 text-4xl font-bold">
          {wallet.data ? formatMoney(wallet.data.balance, wallet.data.currency) : "—"}
        </p>
        <div className="mt-4 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-white/10 px-2.5 py-1">AES-256 encrypted</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1">SHA-256 ledger</span>
          <span className="rounded-full bg-white/10 px-2.5 py-1">TOTP 2FA protected</span>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Icons name="trend" className="h-4 w-4 text-amber-600" /> Commissions paid to platform
          </p>
          <p className="mt-1 text-2xl font-bold text-amber-600">{formatMoney(commissionTotal, "UGX")}</p>
          <p className="text-xs text-slate-400">2.5% per settled order</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <Icons name="truck" className="h-4 w-4 text-emerald-600" /> Settled orders
          </p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{settled.length}</p>
          <p className="text-xs text-slate-400">Released to farmers after confirmation</p>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="mb-3 font-semibold text-slate-900">How it works</h2>
        <ol className="space-y-2 text-sm text-slate-600">
          <li className="flex gap-2"><span className="font-bold text-brand-600">1.</span> Buyer pays into escrow at checkout.</li>
          <li className="flex gap-2"><span className="font-bold text-brand-600">2.</span> Farmer ships the produce.</li>
          <li className="flex gap-2"><span className="font-bold text-brand-600">3.</span> Buyer confirms delivery.</li>
          <li className="flex gap-2"><span className="font-bold text-brand-600">4.</span> Platform deducts 2.5% commission, balance released to farmer.</li>
        </ol>
        <Link href="/orders" className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-brand-600 hover:underline">
          View orders <Icons name="arrow" className="h-3.5 w-3.5" />
        </Link>
      </div>
    </div>
  );
}
