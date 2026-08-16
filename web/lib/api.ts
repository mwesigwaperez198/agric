"use client";

import { useAuthStore } from "@/stores/auth-store";
import { enqueueMutation, isOnline } from "@/lib/offline-queue";
import { API_URL } from "@/lib/utils";

export interface ApiError {
  detail: string;
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const { refreshToken, setTokens, logout } = useAuthStore.getState();
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) throw new Error("refresh failed");
    const body = await res.json();
    setTokens(body.access_token, body.refresh_token);
    return true;
  } catch {
    logout();
    return false;
  }
}

export function getApiUrl(): string {
  return API_URL;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown; formData?: FormData; auth?: boolean; offlineQueue?: boolean } = {}
): Promise<T> {
  const { method = "GET", body, formData, auth = true, offlineQueue = false } = options;
  const url = path.startsWith("http") ? path : `${API_URL}${path}`;

  const headers: Record<string, string> = {};
  if (!formData && body !== undefined) headers["Content-Type"] = "application/json";

  const run = async (): Promise<T> => {
    let token = useAuthStore.getState().accessToken;
    if (auth && token) headers["Authorization"] = `Bearer ${token}`;
    const init: RequestInit = { method, headers };
    if (formData) init.body = formData;
    else if (body !== undefined) init.body = JSON.stringify(body);

    const res = await fetch(url, init);

    if (res.status === 401 && auth) {
      refreshing = refreshing ?? refreshTokens().finally(() => (refreshing = null));
      const ok = await refreshing;
      if (ok) return run();
      throw { detail: "Session expired, please sign in again." } as ApiError;
    }

    if (!res.ok) {
      let detail = res.statusText;
      try {
        const data = await res.json();
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      } catch {
        /* keep statusText */
      }
      throw { detail, status: res.status } as ApiError & { status: number };
    }

    const text = await res.text();
    return (text ? JSON.parse(text) : undefined) as T;
  };

  // Queue write operations when offline for later background sync.
  if (offlineQueue && !isOnline()) {
    enqueueMutation({ url, method, body: formData ? undefined : body });
    return Promise.resolve({ queued: true } as T);
  }

  return run();
}
