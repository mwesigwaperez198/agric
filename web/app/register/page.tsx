"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { DIELECTS, getErrorMessage } from "@/lib/utils";
import { Icons } from "@/components/icons";

export default function RegisterPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    phone: "",
    password: "",
    role: "consumer",
    locale: "en",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function update(key: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/register", {
        body: form,
      });
      setTokens(res.access_token, res.refresh_token);
      const me = await apiFetch<{ id: number; full_name: string; role: string }>("/auth/me");
      setUser(me as never);
      router.push("/dashboard");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="mx-auto flex min-h-[70dvh] max-w-md flex-col justify-center py-8">
      <div className="mb-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-brand-400">
          <Icons name="leaf" className="h-7 w-7" />
        </div>
        <h1 className="mt-4 text-2xl font-bold text-slate-900">Join the farm-to-fork network</h1>
        <p className="text-sm text-slate-500">Direct access. Fair prices. No middlemen.</p>
      </div>

      <form onSubmit={submit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-100 p-1">
          {(["consumer", "farmer"] as const).map((role) => (
            <button
              key={role}
              type="button"
              onClick={() => update("role", role)}
              className={`rounded-lg py-2 text-sm font-semibold capitalize transition-colors ${
                form.role === role ? "bg-white text-brand-700 shadow-sm" : "text-slate-500"
              }`}
            >
              {role === "farmer" ? "Farmer / Seller" : "Consumer"}
            </button>
          ))}
        </div>

        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Full name</span>
          <input required minLength={2} value={form.full_name} onChange={(e) => update("full_name", e.target.value)}
            className={inputCls} placeholder="e.g. Grace Nakato" />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
          <input type="email" required value={form.email} onChange={(e) => update("email", e.target.value)}
            className={inputCls} placeholder="you@example.ug" />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Phone (Mobile Money)</span>
          <input type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)}
            className={inputCls} placeholder="+256 700 000 000" />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Password</span>
          <input type="password" required minLength={8} value={form.password}
            onChange={(e) => update("password", e.target.value)} className={inputCls} placeholder="Minimum 8 characters" />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Preferred language</span>
          <select value={form.locale} onChange={(e) => update("locale", e.target.value)} className={inputCls}>
            {DIELECTS.map((d) => (
              <option key={d.code} value={d.code}>{d.label}</option>
            ))}
          </select>
        </label>

        {error && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        <button type="submit" disabled={busy}
          className="w-full rounded-xl bg-brand-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-50">
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="text-center text-xs text-slate-400">
          By joining you agree to fair-trade principles and escrow-based transactions.
        </p>
      </form>

      <p className="mt-4 text-center text-sm text-slate-500">
        Already registered?{" "}
        <Link href="/login" className="font-semibold text-brand-600 hover:underline">Sign in</Link>
      </p>
    </div>
  );
}
