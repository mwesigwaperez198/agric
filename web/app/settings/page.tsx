"use client";

import { useEffect, useState } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { DIELECTS, getErrorMessage } from "@/lib/utils";
import { flushQueue, peekQueue, type QueuedMutation } from "@/lib/offline-queue";
import { Icons } from "@/components/icons";

type TwoFactorMethod = "totp" | "sms" | "email";

export default function SettingsPage() {
  useRequireAuth();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);

  const [profile, setProfile] = useState({ full_name: "", locale: "en", phone: "" });
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);

  const [selectedMethod, setSelectedMethod] = useState<TwoFactorMethod | null>(null);

  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [provisionUri, setProvisionUri] = useState<string | null>(null);
  const [totpCode, setTotpCode] = useState("");

  const [otpCode, setOtpCode] = useState("");
  const [otpTarget, setOtpTarget] = useState("");
  const [otpCodeSent, setOtpCodeSent] = useState(false);
  const [otpResendCooldown, setOtpResendCooldown] = useState(0);

  const [twofaMsg, setTwofaMsg] = useState<string | null>(null);
  const [twofaError, setTwofaError] = useState<string | null>(null);
  const [twofaBusy, setTwofaBusy] = useState(false);

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

  // ---- TOTP setup ----

  async function setupTotp() {
    setTwofaError(null);
    setTwofaMsg(null);
    setTwofaBusy(true);
    try {
      const res = await apiFetch<{ secret: string; provisioning_uri: string }>("/auth/totp/setup", { method: "POST" });
      setTotpSecret(res.secret);
      setProvisionUri(res.provisioning_uri);
    } catch (err) {
      setTwofaError(getErrorMessage(err));
    } finally {
      setTwofaBusy(false);
    }
  }

  async function enableTotp() {
    setTwofaError(null);
    setTwofaBusy(true);
    try {
      const res = await apiFetch<{ totp_enabled: boolean }>("/auth/totp/enable", { method: "POST", body: { code: totpCode } });
      if (user) setUser({ ...user, totp_enabled: res.totp_enabled, otp_enabled: false, otp_method: null });
      setTwofaMsg("Authenticator app 2FA enabled.");
      setTotpSecret(null);
      setProvisionUri(null);
      setTotpCode("");
      setSelectedMethod(null);
    } catch (err) {
      setTwofaError(getErrorMessage(err));
    } finally {
      setTwofaBusy(false);
    }
  }

  // ---- OTP (SMS / Email) setup ----

  async function sendOtpSetup() {
    setTwofaError(null);
    setTwofaMsg(null);
    if (!selectedMethod || selectedMethod === "totp") return;
    const target = selectedMethod === "sms" ? profile.phone : user?.email;
    if (!target) {
      setTwofaError(selectedMethod === "sms" ? "Add a phone number to your profile first." : "No email on account.");
      return;
    }
    setTwofaBusy(true);
    try {
      await apiFetch("/auth/otp/send", { method: "POST", body: { delivery: selectedMethod } });
      setOtpTarget(target);
      setOtpCodeSent(true);
      startResendCooldown();
    } catch (err) {
      setTwofaError(getErrorMessage(err));
    } finally {
      setTwofaBusy(false);
    }
  }

  async function enableOtp() {
    setTwofaError(null);
    setTwofaBusy(true);
    try {
      const res = await apiFetch<{ otp_enabled: boolean; otp_method: string }>("/auth/otp/setup", {
        method: "POST",
        body: { delivery: selectedMethod, target: selectedMethod === "sms" ? profile.phone : user?.email, code: otpCode },
      });
      if (user) setUser({ ...user, otp_enabled: res.otp_enabled, otp_method: res.otp_method, totp_enabled: false });
      setTwofaMsg(`${selectedMethod === "sms" ? "SMS" : "Email"} 2FA enabled.`);
      setOtpCodeSent(false);
      setOtpCode("");
      setSelectedMethod(null);
    } catch (err) {
      setTwofaError(getErrorMessage(err));
    } finally {
      setTwofaBusy(false);
    }
  }

  async function disableOtp() {
    setTwofaError(null);
    setTwofaBusy(true);
    try {
      const res = await apiFetch<{ otp_enabled: boolean; otp_method: string | null }>("/auth/otp/disable", { method: "POST" });
      if (user) setUser({ ...user, otp_enabled: res.otp_enabled, otp_method: res.otp_method });
      setTwofaMsg("OTP 2FA disabled.");
      setSelectedMethod(null);
    } catch (err) {
      setTwofaError(getErrorMessage(err));
    } finally {
      setTwofaBusy(false);
    }
  }

  function startResendCooldown() {
    setOtpResendCooldown(60);
    const interval = setInterval(() => {
      setOtpResendCooldown((prev) => {
        if (prev <= 1) { clearInterval(interval); return 0; }
        return prev - 1;
      });
    }, 1000);
  }

  function reset2faUI() {
    setSelectedMethod(null);
    setTotpSecret(null);
    setProvisionUri(null);
    setTotpCode("");
    setOtpCode("");
    setOtpCodeSent(false);
    setTwofaMsg(null);
    setTwofaError(null);
  }

  // ---- Offline sync ----

  async function syncNow() {
    setSyncing(true);
    try {
      const n = await flushQueue();
      setQueue(peekQueue());
      setTwofaMsg(n > 0 ? `Replayed ${n} queued mutation(s).` : "Queue is empty.");
    } finally {
      setSyncing(false);
    }
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  const isCurrently2faEnabled = user?.totp_enabled || user?.otp_enabled;
  const activeMethodLabel = user?.totp_enabled ? "Authenticator app" : user?.otp_method === "sms" ? "SMS" : user?.otp_method === "email" ? "Email" : null;

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

      {/* ---- Two-factor authentication ---- */}
      <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-semibold text-slate-900">
          <Icons name="shield" className="h-4 w-4 text-brand-600" /> Two-factor authentication
        </h2>

        {isCurrently2faEnabled && !selectedMethod && (
          <div className="space-y-3">
            <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              2FA is enabled via <span className="font-semibold">{activeMethodLabel}</span>.
            </p>
            <div className="flex gap-2">
              <button onClick={reset2faUI}
                className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200">
                Change method
              </button>
              {user?.otp_enabled && (
                <button onClick={disableOtp} disabled={twofaBusy}
                  className="rounded-xl bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50">
                  {twofaBusy ? "Disabling…" : "Disable OTP"}
                </button>
              )}
            </div>
          </div>
        )}

        {!isCurrently2faEnabled && !selectedMethod && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">Choose a method to secure your account with two-factor authentication.</p>
            <div className="space-y-2">
              <button onClick={() => { setSelectedMethod("totp"); setupTotp(); }}
                className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-3 text-left hover:border-brand-400 hover:bg-brand-50">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-lg">🔑</span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Authenticator app</p>
                  <p className="text-xs text-slate-500">Use Google Authenticator, Authy, or similar</p>
                </div>
              </button>
              <button onClick={() => setSelectedMethod("sms")}
                className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-3 text-left hover:border-brand-400 hover:bg-brand-50">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-lg">📱</span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">SMS to {profile.phone || "add phone in profile"}</p>
                  <p className="text-xs text-slate-500">Receive a code via text message</p>
                </div>
              </button>
              <button onClick={() => setSelectedMethod("email")}
                className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-3 text-left hover:border-brand-400 hover:bg-brand-50">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-lg">📧</span>
                <div>
                  <p className="text-sm font-semibold text-slate-900">Email to {user?.email}</p>
                  <p className="text-xs text-slate-500">Receive a code via email</p>
                </div>
              </button>
            </div>
          </div>
        )}

        {/* TOTP setup flow */}
        {selectedMethod === "totp" && totpSecret && (
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
              <button onClick={enableTotp} disabled={twofaBusy}
                className="rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700 disabled:opacity-50">
                {twofaBusy ? "Verifying…" : "Enable"}
              </button>
            </div>
          </div>
        )}

        {/* OTP setup flow (SMS / Email) */}
        {selectedMethod && selectedMethod !== "totp" && (
          <div className="space-y-3">
            {!otpCodeSent ? (
              <>
                <p className="text-sm text-slate-600">
                  We&apos;ll send a 6-digit code to your {selectedMethod === "sms" ? "phone" : "email"} to verify setup.
                </p>
                <div className="flex gap-2">
                  <button onClick={sendOtpSetup} disabled={twofaBusy}
                    className="rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700 disabled:opacity-50">
                    {twofaBusy ? "Sending…" : "Send code"}
                  </button>
                  <button onClick={reset2faUI}
                    className="rounded-xl bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-200">
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <p className="text-sm text-slate-600">
                  Code sent to {otpTarget}. Enter it below to enable {selectedMethod === "sms" ? "SMS" : "email"} 2FA.
                </p>
                <div className="flex gap-2">
                  <input inputMode="numeric" maxLength={6} value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/\D/g, ""))}
                    className={`${inputCls} w-32 text-center text-lg tracking-[0.4em]`} placeholder="000000" />
                  <button onClick={enableOtp} disabled={twofaBusy || otpCode.length < 6}
                    className="rounded-xl bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700 disabled:opacity-50">
                    {twofaBusy ? "Verifying…" : "Enable"}
                  </button>
                </div>
                <button onClick={sendOtpSetup} disabled={otpResendCooldown > 0 || twofaBusy}
                  className="text-xs font-medium text-blue-600 hover:underline disabled:text-slate-400">
                  {otpResendCooldown > 0 ? `Resend in ${otpResendCooldown}s` : "Resend code"}
                </button>
              </>
            )}
          </div>
        )}

        {twofaMsg && <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{twofaMsg}</p>}
        {twofaError && <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{twofaError}</p>}
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
