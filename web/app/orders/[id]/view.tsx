"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { StatusBadge, Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { formatMoney, formatDateTime, getErrorMessage } from "@/lib/utils";

interface Order {
  id: number;
  buyer_id: number;
  seller_id: number;
  quantity: number;
  unit_price: number;
  total: number;
  currency: string;
  commission_amount: number;
  farmer_net: number;
  status: string;
  delivery_notes?: string | null;
  delivery_proof_url?: string | null;
  created_at: string;
}

interface LedgerEntry {
  id: number;
  entry_type: string;
  amount: number;
  balance_after: number;
  reference: string;
  sha256_hash: string;
  note?: string | null;
  created_at: string;
}

const LEDGER_ICONS: Record<string, string> = { deposit: "wallet", commission: "trend", release: "truck", refund: "arrow" };
const LEDGER_COLORS: Record<string, string> = {
  deposit: "bg-blue-50 text-blue-700",
  commission: "bg-amber-50 text-amber-700",
  release: "bg-emerald-50 text-emerald-700",
  refund: "bg-slate-100 text-slate-600",
};

export default function OrderDetailView() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const [order, setOrder] = useState<Order | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const [o, l, b] = await Promise.all([
          apiFetch<Order>(`/orders/${params.id}`),
          apiFetch<LedgerEntry[]>(`/orders/${params.id}/ledger`),
          apiFetch<{ escrow_balance: number }>(`/orders/${params.id}/balance`),
        ]);
        setOrder(o);
        setLedger(l);
        setBalance(b.escrow_balance);
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    })();
  }, [params.id]);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/orders/${params.id}/confirm`, {
        body: { proof_url: null, note: "Delivery confirmed in app" },
      });
      router.refresh();
      window.location.reload();
    } catch (err) {
      setError(getErrorMessage(err));
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/orders/${params.id}/cancel`, { body: {} });
      router.refresh();
      window.location.reload();
    } catch (err) {
      setError(getErrorMessage(err));
      setBusy(false);
    }
  }

  if (loading) return <Spinner />;
  if (!order) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-xl font-bold text-slate-700">{error ?? "Order not found"}</h1>
        <Link href="/orders" className="mt-2 inline-block text-brand-600 hover:underline">Back to orders</Link>
      </div>
    );
  }

  const isBuyer = user?.id === order.buyer_id;
  const canConfirm = isBuyer && ["in_escrow", "shipped"].includes(order.status);
  const canCancel = ["in_escrow", "pending"].includes(order.status) && (isBuyer || user?.id === order.seller_id);

  return (
    <div className="animate-fade-in space-y-5">
      <Link href="/orders" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-500 hover:text-slate-800">
        <Icons name="chevron" className="h-4 w-4 rotate-180" /> All orders
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Order #{order.id}</h1>
          <p className="text-sm text-slate-500">Placed {formatDateTime(order.created_at)}</p>
        </div>
        <StatusBadge status={order.status} />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 font-semibold text-slate-900">Transaction</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between text-slate-600">
                <span>Quantity</span><span>{order.quantity} units @ {formatMoney(order.unit_price, order.currency)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Total paid into escrow</span><span className="font-semibold text-slate-900">{formatMoney(order.total, order.currency)}</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Platform commission (2.5%)</span><span className="font-semibold text-amber-600">{formatMoney(order.commission_amount, order.currency)}</span>
              </div>
              <div className="flex justify-between border-t border-slate-100 pt-2 text-slate-600">
                <span>Farmer receives</span><span className="font-bold text-emerald-600">{formatMoney(order.farmer_net, order.currency)}</span>
              </div>
              <div className="flex justify-between rounded-xl bg-slate-50 px-3 py-2">
                <span>Escrow balance</span>
                <span className="font-bold text-slate-900">{balance != null ? formatMoney(balance, order.currency) : "—"}</span>
              </div>
            </div>
          </div>

          {canConfirm && (
            <div className="rounded-2xl border border-brand-200 bg-brand-50 p-5">
              <h2 className="flex items-center gap-2 font-semibold text-brand-800">
                <Icons name="check" className="h-4 w-4" /> Received your order?
              </h2>
              <p className="mt-1 text-sm text-brand-700">
                Confirm to release funds from escrow to the farmer. The 2.5% commission is deducted automatically.
              </p>
              <div className="mt-3 flex gap-2">
                <button onClick={confirm} disabled={busy} className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
                  {busy ? "Confirming…" : "Confirm delivery"}
                </button>
                <button onClick={cancel} disabled={busy} className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
                  Cancel order
                </button>
              </div>
              {error && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            </div>
          )}
          {canCancel && !canConfirm && (
            <button onClick={cancel} disabled={busy} className="w-full rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50">
              {busy ? "Cancelling…" : "Cancel order (refund to wallet)"}
            </button>
          )}

          {order.delivery_proof_url && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="mb-1 flex items-center gap-2 font-semibold text-slate-900">
                <Icons name="camera" className="h-4 w-4 text-brand-600" /> Delivery proof
              </h2>
              <a href={order.delivery_proof_url} target="_blank" rel="noreferrer" className="text-sm text-brand-600 hover:underline">
                {order.delivery_proof_url}
              </a>
              {order.delivery_notes && <p className="mt-1 text-sm text-slate-500">{order.delivery_notes}</p>}
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="mb-4 flex items-center gap-2 font-semibold text-slate-900">
            <Icons name="shield" className="h-4 w-4 text-brand-600" /> Escrow ledger
          </h2>
          {ledger.length === 0 ? (
            <p className="text-sm text-slate-500">No ledger entries yet.</p>
          ) : (
            <ol className="relative space-y-4 border-l border-slate-200 pl-5">
              {ledger.map((entry) => (
                <li key={entry.id} className="relative">
                  <span className={`absolute -left-[29px] rounded-full p-1.5 ${LEDGER_COLORS[entry.entry_type] ?? "bg-slate-100 text-slate-600"}`}>
                    <Icons name={LEDGER_ICONS[entry.entry_type] ?? "spark"} className="h-3.5 w-3.5" />
                  </span>
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold capitalize text-slate-800">
                      {entry.entry_type.replace("_", " ")}
                      <span className="ml-2 text-xs font-normal text-slate-400">{formatDateTime(entry.created_at)}</span>
                    </p>
                    <p className={`text-sm font-bold ${entry.amount < 0 ? "text-red-600" : "text-emerald-600"}`}>
                      {entry.amount < 0 ? "−" : "+"}{formatMoney(Math.abs(entry.amount), order.currency)}
                    </p>
                  </div>
                  <p className="text-xs text-slate-500">{entry.note}</p>
                  <p className="mt-0.5 break-all font-mono text-[10px] text-slate-400" title={entry.sha256_hash}>
                    sha256:{entry.sha256_hash.slice(0, 20)}…
                  </p>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
