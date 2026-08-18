"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch, getApiUrl } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { APP_NAME, getErrorMessage } from "@/lib/utils";
import { Icons } from "@/components/icons";

export default function LoginPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [totpRequired, setTotpRequired] = useState(false);
  const [otpRequired, setOtpRequired] = useState(false);
  const [otpTarget, setOtpTarget] = useState("");
  const [otpResendCooldown, setOtpResendCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiFetch<{
        access_token: string;
        refresh_token: string;
        totp_required: boolean;
        otp_required: boolean;
        otp_target: string | null;
      }>("/auth/login", { method: "POST", body: { email, password } });
      if (res.totp_required) {
        setTotpRequired(true);
        return;
      }
      if (res.otp_required) {
        setOtpRequired(true);
        setOtpTarget(res.otp_target ?? "");
        startResendCooldown();
        return;
      }
      await completeLogin(res.access_token, res.refresh_token);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitTotp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/totp/login", {
        method: "POST",
        body: { email, password, code },
      });
      await completeLogin(res.access_token, res.refresh_token);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitOtp(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await apiFetch<{ access_token: string; refresh_token: string }>("/auth/otp/verify", {
        method: "POST",
        body: { email, password, code },
      });
      await completeLogin(res.access_token, res.refresh_token);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function resendOtp() {
    setError(null);
    try {
      await apiFetch("/auth/otp/send", { method: "POST", body: { delivery: "sms" } });
      startResendCooldown();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  function startResendCooldown() {
    setOtpResendCooldown(60);
    const interval = setInterval(() => {
      setOtpResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }

  async function completeLogin(access: string, refresh: string) {
    setTokens(access, refresh);
    try {
      const me = await apiFetch<{ id: number; full_name: string; role: string }>("/auth/me");
      setUser(me as never);
    } catch {
      /* profile loads lazily */
    }
    router.push("/dashboard");
  }

  const isSecondFactor = totpRequired || otpRequired;

  return (
    <div className="mx-auto flex min-h-[70dvh] max-w-md flex-col justify-center py-8">
      <div className="mb-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-ink-900 text-brand-400">
          <Icons name="leaf" className="h-7 w-7" />
        </div>
        <h1 className="mt-4 text-2xl font-bold text-slate-900">Welcome back</h1>
        <p className="text-sm text-slate-500">{APP_NAME} · Sign in to continue</p>
      </div>

      <form onSubmit={totpRequired ? submitTotp : otpRequired ? submitOtp : login} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {!isSecondFactor && (
          <>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                placeholder="you@example.ug"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Password</span>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
                placeholder="••••••••"
              />
            </label>
          </>
        )}

        {totpRequired && (
          <div className="space-y-3 rounded-xl bg-blue-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
              <Icons name="shield" className="h-4 w-4" /> Two-factor authentication
            </div>
            <p className="text-xs text-blue-700">
              Enter the 6-digit code from your authenticator app to complete sign-in.
            </p>
            <input
              inputMode="numeric"
              autoFocus
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="w-full rounded-xl border border-blue-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.5em] focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              placeholder="000000"
            />
          </div>
        )}

        {otpRequired && (
          <div className="space-y-3 rounded-xl bg-blue-50 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
              <Icons name="shield" className="h-4 w-4" /> Verification code
            </div>
            <p className="text-xs text-blue-700">
              {otpTarget
                ? `We sent a 6-digit code to ${otpTarget}. Enter it below to complete sign-in.`
                : "Enter the 6-digit code sent to your phone or email."}
            </p>
            <input
              inputMode="numeric"
              autoFocus
              required
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="w-full rounded-xl border border-blue-300 bg-white px-3 py-2.5 text-center text-lg tracking-[0.5em] focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
              placeholder="000000"
            />
            <button
              type="button"
              onClick={resendOtp}
              disabled={otpResendCooldown > 0}
              className="text-xs font-medium text-blue-600 hover:underline disabled:text-slate-400"
            >
              {otpResendCooldown > 0 ? `Resend in ${otpResendCooldown}s` : "Resend code"}
            </button>
          </div>
        )}

        {error && (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-brand-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
        >
          {busy ? "Signing in…" : isSecondFactor ? "Verify code" : "Sign in"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-slate-500">
        New here?{" "}
        <Link href="/register" className="font-semibold text-brand-600 hover:underline">
          Create an account
        </Link>
      </p>
    </div>
  );
}
