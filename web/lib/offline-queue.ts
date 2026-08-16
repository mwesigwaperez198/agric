"use client";

/* Offline-first mutation queue with background sync.
 * Failed write operations are persisted to localStorage and replayed when
 * the network recovers. Respects rural network outages per the offline-first
 * architecture requirement.
 */

export interface QueuedMutation {
  id: string;
  url: string;
  method: string;
  body?: unknown;
  createdAt: number;
}

const QUEUE_KEY = "farm2fork-mutation-queue";
export const MAX_QUEUE = 100;

export function isOnline(): boolean {
  return typeof navigator !== "undefined" ? navigator.onLine : true;
}

function readQueue(): QueuedMutation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    return raw ? (JSON.parse(raw) as QueuedMutation[]) : [];
  } catch {
    return [];
  }
}

function writeQueue(queue: QueuedMutation[]): void {
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE)));
}

export function enqueueMutation(mutation: Omit<QueuedMutation, "id" | "createdAt">): void {
  const queue = readQueue();
  queue.push({ ...mutation, id: crypto.randomUUID?.() ?? String(Date.now()), createdAt: Date.now() });
  writeQueue(queue);
}

export function peekQueue(): QueuedMutation[] {
  return readQueue();
}

export function clearQueue(): void {
  localStorage.removeItem(QUEUE_KEY);
}

export async function flushQueue(): Promise<number> {
  const queue = readQueue();
  if (queue.length === 0) return 0;
  let replayed = 0;
  for (const mutation of queue) {
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const token = localStorage.getItem("farm2fork-auth");
      if (token) {
        const parsed = JSON.parse(token);
        if (parsed.state?.accessToken) headers["Authorization"] = `Bearer ${parsed.state.accessToken}`;
      }
      const res = await fetch(mutation.url, {
        method: mutation.method,
        headers,
        body: mutation.body ? JSON.stringify(mutation.body) : undefined,
      });
      if (res.ok || res.status === 409 || res.status === 400) replayed += 1;
      else return replayed; // stop on server errors, keep the rest queued
    } catch {
      return replayed; // still offline, keep queue
    }
  }
  clearQueue();
  return replayed;
}

export function registerSync(): void {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
  navigator.serviceWorker.ready.then((reg) => {
    const sync = (reg as ServiceWorkerRegistration & { sync?: { register: (tag: string) => Promise<void> } }).sync;
    sync?.register("flush-mutations").catch(() => {});
  });
  navigator.serviceWorker.addEventListener("message", (event) => {
    if (event.data && event.data.type === "FLUSH_MUTATIONS") {
      flushQueue();
    }
  });
  window.addEventListener("online", () => {
    flushQueue();
  });
}
