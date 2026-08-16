"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { DIELECTS, getErrorMessage } from "@/lib/utils";
import { flushQueue, peekQueue, type QueuedMutation } from "@/lib/offline-queue";
import { Icons } from "@/components/icons";

export default function SettingsPage() {
  useRequireAuth();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const [profile, setProfile] = useState({ full_name: "", locale: "en", phone: "" });
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [provisionUri, setProvisionUri] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [totpMsg, setTotpMsg] = useState<string | null>(null);

  const [queue, setQueue] = useState<QueuedMutation[]>([]);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    if (user) setProfile({ full_name: user.full_name, locale: user.locale, phone: user.phone ?? "" });
    setQueue(peekQueue());
  }, [user]);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setProfileError(null);
    try {
      const res = await apiFetch<{ full_name: string; locale: string; phone: string | null }>("/me", {
        method: "PATCH",
        body: profile,
      });
      if (user) setUser({ ...user, full_name: res.full_name, locale: res.locale, phone: res.phone });
      setSaved(true);
    } catch (err) {
      setProfileError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function setupTotp() {
    try {
      const res = await apiFetch<{ secret: string; provisioning_uri: string }>("/auth/totp/setup", { method: "POST" });
      setTotpSecret(res.secret);
      setProvisionUri(res.provisioning_uri);
      setTotpMsg(null);
    } catch (err) {
      setTotpMsg(getErrorMessage(err));
    }
  }

  async function enableTotp() {
    try {
      const res = await apiFetch<{ totp_enabled: boolean }>("/auth/totp/enable", { method: "POST", body: { code: totpCode } });
      if (user) setUser({ ...user, totp_enabled: res.totp_enabled });
      setTotpMsg("Two-factor authentication enabled.");
      setTotpSecret(null);
      setProvisionUri(null);
      setTotpCode("");
    } catch (err) {
      setTotpMsg(getErrorMessage(err));
    }
  }

  async function syncNow() {
    setSyncing(true);
    try {
      const n = await flushQueue();
      setQueue(peekQueue());
      setTotpMsg(n > 0 ? `Replayed ${n} queued mutation(s).` : "Queue is empty.");
    } finally {
      setSyncing(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="text-sm text-slate-500">Profile, security and offline sync.</p>
      </div>

      <form onSubmit={saveProfile} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold text-slate-900">Profile</h2>
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Full name</span>
          <input required value={profile.full_name} onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
            className={inputCls} />
        </label>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Phone</span>
            <input value={profile.phone} onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
              className={inputCls} placeholder="+256 700 000 000" />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium text-slate-700">Language</span>
            <select value={profile.locale} onChange={(e) => setProfile({ ...profile, locale: e.target.value })} className={inputCls}>
              {DIELECTS.map((d) => (
                <option key={d.code} value={d.code}>{d.label}</option>
              ))}
            </select>
          </label>
        </div>
        {saved && <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">Profile saved.</p>}
        {profileError && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{profileError}</p>}
        <button type="submit" disabled={saving}
          className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
          {saving ? "Saving…" : "Save profile"}
        </button>
      </form>

      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="shield" className="h-4 w-4 text-brand-600" /> Two-factor authentication
        </h2>
        {user?.totp_enabled ? (
          <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            TOTP 2FA is enabled for this account.
          </p>
        ) : totpSecret ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Scan this QR with your authenticator app, or enter the secret manually:
            </p>
            <p className="rounded-lg bg-slate-100 p-3 font-mono text-sm break-all">{totpSecret}</p>
            {provisionUri && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={`https://api.qrserver.com/v1/create-qr-code/?data=${encodeURIComponent(provisionUri)}&size=160x160`}
                alt="TOTP QR code" className="rounded-xl border border-slate-200" />
            )}
            <div className="flex gap-2">
              <input inputMode="numeric" maxLength={6} value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                className={`${inputCls} w-32 text-center text-lg tracking-[0.4em]`} placeholder="000000" />
              <button onClick={enableTotp}
                className="rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700">
                Enable
              </button>
            </div>
          </div>
        ) : (
          <button onClick={setupTotp}
            className="rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-700">
            Set up 2FA
          </button>
        )}
        {totpMsg && <p className="rounded-xl bg-slate-50 px-3 py-2 text-sm text-slate-600">{totpMsg}</p>}
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="activity" className="h-4 w-4 text-brand-600" /> Offline sync
        </h2>
        <p className="text-sm text-slate-500">
          {queue.length} queued action(s) waiting to sync when the network recovers.
        </p>
        <div className="flex items-center gap-2">
          <button onClick={syncNow} disabled={syncing}
            className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
            {syncing ? "Syncing…" : "Sync now"}
          </button>
          <span className="text-xs text-slate-400">Auto-syncs on reconnect via the service worker.</span>
        </div>
      </div>
    </div>
  );
}
