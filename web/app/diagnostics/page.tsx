"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { DIELECTS, getErrorMessage } from "@/lib/utils";

interface VoiceAnswer {
  answer: string;
  translated?: string | null;
  tts_audio_url?: string | null;
  guardrail: boolean;
  dialect: string;
}

interface Diagnostic {
  id: number;
  prediction: { label: string };
  advice?: string | null;
  created_at: string;
}

interface ChatHistoryEntry {
  id: number;
  role: string;
  content: string;
  language: string;
  created_at: string;
}

interface ChatMsg {
  role: "user" | "assistant";
  text: string;
  ttsUrl?: string | null;
  error?: boolean;
}

const SUGGESTIONS = [
  { icon: "🌱", text: "How do I plant maize?" },
  { icon: "☕", text: "My coffee leaves have yellow spots" },
  { icon: "🐔", text: "How do I raise chickens?" },
  { icon: "🌧", text: "When should I plant this season?" },
];

function renderMarkdown(text: string): string {
  let html = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-bold text-slate-900 mt-3 mb-1">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-slate-900 mt-4 mb-1">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-slate-900 mt-4 mb-1">$1</h1>');

  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold">$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

  html = html.replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>');
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal">$2</li>');

  html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, (match) => `<ul class="my-1 space-y-0.5">${match}</ul>`);

  html = html.replace(/`([^`]+)`/g, '<code class="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono">$1</code>');

  html = html.replace(/\n{2,}/g, '</p><p class="mt-2">');
  html = html.replace(/\n/g, '<br/>');

  return `<p>${html}</p>`;
}

export default function DiagnosticsPage() {
  useRequireAuth();

  const [locale, setLocale] = useState("en");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [historyData, setHistoryData] = useState<ChatHistoryEntry[] | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [playingAudio, setPlayingAudio] = useState<number | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const scroll = useCallback(() => {
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 80);
  }, []);

  useEffect(() => {
    scroll();
  }, [messages, scroll]);

  useEffect(() => {
    return () => {
      if (imagePreview) URL.revokeObjectURL(imagePreview);
      audioRef.current?.pause();
    };
  }, [imagePreview]);

  async function send(text: string, retryIndex?: number) {
    const q = text.trim();
    if (!q || busy) return;
    setInput("");
    setBusy(true);
    setError(null);

    if (retryIndex !== undefined) {
      setMessages((prev) => prev.map((m, i) => i === retryIndex ? { ...m, error: false } : m));
    } else {
      setMessages((prev) => [...prev, { role: "user", text: q }]);
    }

    try {
      const res = await apiFetch<VoiceAnswer>("/voice/chat", {
        method: "POST",
        body: { text: q, locale, crop_type: "general" },
      });
      const reply = res.translated || res.answer;
      setMessages((prev) => {
        if (retryIndex !== undefined) {
          const updated = [...prev];
          updated[retryIndex + 1] = { role: "assistant", text: reply, ttsUrl: res.tts_audio_url };
          return updated;
        }
        return [...prev, { role: "assistant", text: reply, ttsUrl: res.tts_audio_url }];
      });
    } catch (err) {
      setError(getErrorMessage(err));
      if (retryIndex !== undefined) {
        setMessages((prev) => prev.map((m, i) => i === retryIndex + 1 ? { ...m, error: true } : m));
      }
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function clearChat() {
    setMessages([]);
    setError(null);
    audioRef.current?.pause();
    setPlayingAudio(null);
  }

  async function loadHistory() {
    if (showHistory) {
      setShowHistory(false);
      return;
    }
    setHistoryLoading(true);
    setShowHistory(true);
    try {
      const data = await apiFetch<ChatHistoryEntry[]>("/voice/history?limit=30");
      setHistoryData(data);
    } catch {
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  function restoreHistory() {
    if (!historyData || historyData.length === 0) return;
    const pairs: ChatMsg[] = [];
    for (let i = 0; i < historyData.length - 1; i++) {
      if (historyData[i].role === "user" && historyData[i + 1].role === "assistant") {
        pairs.push({ role: "user", text: historyData[i].content });
        pairs.push({ role: "assistant", text: historyData[i + 1].content });
        i++;
      }
    }
    setMessages(pairs.slice(-10));
    setShowHistory(false);
    scroll();
  }

  async function analyzePhoto() {
    if (!image) return;
    setAnalyzing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", image);
      form.append("crop_type", "auto");
      const res = await apiFetch<Diagnostic>("/diagnostics/analyze", { method: "POST", formData: form });
      const advice = res.advice || "I analyzed your photo but couldn't find a specific issue.";
      setMessages((prev) => [
        ...prev,
        { role: "user", text: "[Photo uploaded]" },
        { role: "assistant", text: advice },
      ]);
      if (imagePreview) URL.revokeObjectURL(imagePreview);
      setImage(null);
      setImagePreview(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  }

  function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImage(f);
    setImagePreview(f ? URL.createObjectURL(f) : null);
  }

  async function onVoice(text: string, _lang?: string, englishText?: string) {
    if (!text.trim()) return;
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", text }]);
    setError(null);
    try {
      const res = await apiFetch<VoiceAnswer>("/voice/chat", {
        method: "POST",
        body: {
          text,
          locale,
          crop_type: "general",
          detected_language: _lang || locale,
          english_text: englishText || text,
        },
      });
      const reply = res.translated || res.answer;
      setMessages((prev) => [...prev, { role: "assistant", text: reply, ttsUrl: res.tts_audio_url }]);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function playTts(url: string, msgIndex: number) {
    if (audioRef.current) {
      audioRef.current.pause();
      if (playingAudio === msgIndex) {
        setPlayingAudio(null);
        return;
      }
    }
    const audio = new Audio(url);
    audio.onended = () => setPlayingAudio(null);
    audio.onerror = () => {
      setPlayingAudio(null);
      speak(messages[msgIndex].text);
    };
    audioRef.current = audio;
    audio.play();
    setPlayingAudio(msgIndex);
  }

  function speak(text: string) {
    if (!("speechSynthesis" in window)) return;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = locale === "lg" ? "lg" : locale === "sw" ? "sw" : "en-UG";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  }

  const hasChat = messages.length > 0;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-bold text-white">
              N
            </div>
            <div>
              <h1 className="text-sm font-bold text-slate-900">NOVA Assistant</h1>
              <p className="text-xs text-slate-500">Ugandan Agriculture AI</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasChat && (
              <button
                onClick={clearChat}
                className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100"
                title="New conversation"
              >
                <Icons name="trash" className="h-4 w-4" />
              </button>
            )}
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value)}
              className="rounded-lg border-0 bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600 focus:ring-2 focus:ring-brand-500"
            >
              {DIELECTS.map((d) => (
                <option key={d.code} value={d.code}>{d.label}</option>
              ))}
            </select>
            <button
              onClick={loadHistory}
              className="rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100"
              title="Recent conversations"
            >
              <Icons name="clock" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      {/* History panel */}
      {showHistory && (
        <div className="border-b border-slate-200 bg-white">
          <div className="mx-auto max-w-2xl px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase text-slate-400">Recent Conversations</h3>
              <div className="flex gap-2">
                {historyData && historyData.length > 0 && (
                  <button
                    onClick={restoreHistory}
                    className="rounded-md bg-brand-50 px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-100"
                  >
                    Continue here
                  </button>
                )}
                <button onClick={() => setShowHistory(false)} className="text-xs text-slate-400 hover:text-slate-600">
                  Close
                </button>
              </div>
            </div>
            {historyLoading ? (
              <Spinner />
            ) : historyData && historyData.length > 0 ? (
              <div className="max-h-48 space-y-1 overflow-y-auto">
                {historyData.slice(-20).reverse().map((entry) => (
                  <div
                    key={entry.id}
                    className={`rounded-lg px-3 py-2 text-xs ${
                      entry.role === "user"
                        ? "bg-blue-50 text-blue-800"
                        : "bg-slate-50 text-slate-700"
                    }`}
                  >
                    <span className="font-semibold">{entry.role === "user" ? "You: " : "NOVA: "}</span>
                    {entry.content.slice(0, 100)}{entry.content.length > 100 ? "..." : ""}
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-4 text-center text-xs text-slate-400">No conversations yet</p>
            )}
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-6">
          {!hasChat ? (
            /* Empty state */
            <div className="flex flex-col items-center pt-12 text-center">
              <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-brand-400 to-brand-600 shadow-lg shadow-brand-500/25">
                <Icons name="spark" className="h-10 w-10 text-white" />
              </div>
              <h2 className="mb-1 text-xl font-bold text-slate-900">Hello! I&apos;m NOVA</h2>
              <p className="mb-8 max-w-sm text-sm text-slate-500">
                Ask me anything about farming in Uganda — crops, livestock, soil, weather, or market prices.
              </p>
              <div className="grid w-full grid-cols-2 gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.text}
                    onClick={() => send(s.text)}
                    className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white p-3 text-left text-sm text-slate-700 shadow-sm transition-all hover:border-brand-300 hover:shadow-md"
                  >
                    <span className="mt-0.5 text-base">{s.icon}</span>
                    <span>{s.text}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Messages */
            <div className="space-y-4">
              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`flex max-w-[85%] flex-col gap-1 ${m.role === "user" ? "items-end" : "items-start"}`}>
                    <div
                      className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                        m.role === "user"
                          ? "bg-brand-600 text-white rounded-br-md"
                          : "bg-white text-slate-800 shadow-sm border border-slate-100 rounded-bl-md"
                      }`}
                    >
                      {m.role === "assistant" ? (
                        <div
                          className="prose prose-sm max-w-none prose-headings:text-slate-900 prose-strong:text-slate-900 prose-li:text-slate-700"
                          dangerouslySetInnerHTML={{ __html: renderMarkdown(m.text) }}
                        />
                      ) : (
                        <div className="whitespace-pre-line">{m.text}</div>
                      )}
                    </div>
                    {m.role === "assistant" && (
                      <div className="flex items-center gap-2">
                        {m.ttsUrl && (
                          <button
                            onClick={() => playTts(m.ttsUrl!, i)}
                            className={`flex items-center gap-1 px-2 text-xs hover:text-brand-600 ${
                              playingAudio === i ? "text-brand-600" : "text-slate-400"
                            }`}
                          >
                            <Icons name="mic" className="h-3 w-3" />
                            {playingAudio === i ? "Stop" : "Listen"}
                          </button>
                        )}
                        {!m.ttsUrl && (
                          <button
                            onClick={() => speak(m.text)}
                            className="flex items-center gap-1 px-2 text-xs text-slate-400 hover:text-brand-600"
                          >
                            <Icons name="mic" className="h-3 w-3" /> Listen
                          </button>
                        )}
                        {i === messages.length - 1 && m.error && !busy && (
                          <button
                            onClick={() => {
                              const userMsg = messages[i - 1];
                              if (userMsg?.role === "user") send(userMsg.text, i - 1);
                            }}
                            className="flex items-center gap-1 px-2 text-xs text-red-400 hover:text-red-600"
                          >
                            Retry
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {busy && (
                <div className="flex justify-start">
                  <div className="rounded-2xl rounded-bl-md border border-slate-100 bg-white px-4 py-3 shadow-sm">
                    <div className="flex items-center gap-2 text-sm text-slate-400">
                      <div className="flex gap-1">
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.3s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300 [animation-delay:-0.15s]" />
                        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-slate-300" />
                      </div>
                      Thinking...
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-auto max-w-2xl px-4 pb-2">
          <div className="rounded-xl bg-red-50 px-4 py-2.5 text-sm text-red-700">{error}</div>
        </div>
      )}

      {/* Input area */}
      <div className="sticky bottom-0 border-t border-slate-200 bg-white/80 backdrop-blur-md safe-bottom">
        <div className="mx-auto max-w-2xl px-4 py-3">
          {/* Photo analyze bar */}
          {(image || analyzing) && (
            <div className="mb-2 flex items-center gap-2 rounded-xl bg-slate-50 px-3 py-2">
              {imagePreview && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imagePreview} alt="" className="h-8 w-8 rounded-lg object-cover" />
              )}
              <span className="flex-1 text-xs text-slate-600">{analyzing ? "Analyzing photo..." : "Photo ready"}</span>
              {!analyzing && (
                <>
                  <button onClick={analyzePhoto} className="rounded-lg bg-brand-500 px-3 py-1 text-xs font-semibold text-white hover:bg-brand-600">
                    Check
                  </button>
                  <button onClick={() => { if (imagePreview) URL.revokeObjectURL(imagePreview); setImage(null); setImagePreview(null); }} className="text-xs text-slate-400 hover:text-red-500">
                    Cancel
                  </button>
                </>
              )}
            </div>
          )}

          <div className="flex items-center gap-2">
            {/* Camera button */}
            <label className="flex h-10 w-10 flex-shrink-0 cursor-pointer items-center justify-center rounded-xl bg-slate-100 text-slate-500 hover:bg-slate-200">
              <Icons name="camera" className="h-4 w-4" />
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageSelect}
              />
            </label>

            {/* Voice button */}
            <VoiceBtn onResult={onVoice} />

            {/* Text input */}
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !busy && send(input)}
              placeholder="Ask about farming..."
              className="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200"
              disabled={busy}
            />

            {/* Send button */}
            <button
              onClick={() => send(input)}
              disabled={busy || !input.trim()}
              className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white hover:bg-brand-700 disabled:opacity-40"
            >
              <Icons name="check" className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* Voice button with inline recorder */
function VoiceBtn({ onResult }: { onResult: (text: string, lang?: string, eng?: string) => void }) {
  const [state, setState] = useState<"idle" | "recording" | "sending">("idle");
  const [error, setError] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  function getMimeType(): string {
    for (const t of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]) {
      if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
  }

  async function start() {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Voice not supported");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream, { mimeType: getMimeType() || undefined });
      mediaRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      rec.onstop = send;
      rec.start();
      setState("recording");
      setTimeout(() => { if (rec.state === "recording") rec.stop(); }, 30000);
    } catch {
      setError("Mic blocked");
      setState("idle");
    }
  }

  function stop() {
    mediaRef.current?.stop();
    mediaRef.current?.stream.getTracks().forEach((t) => t.stop());
  }

  async function send() {
    if (!chunksRef.current.length) { setState("idle"); return; }
    setState("sending");
    const blob = new Blob(chunksRef.current, { type: chunksRef.current[0]?.type || "audio/webm" });
    const form = new FormData();
    form.append("file", blob, "voice.webm");
    try {
      const res = await apiFetch<{ text: string; detected_language: string; english_text: string }>("/voice/transcribe", {
        method: "POST",
        formData: form,
      });
      if (res.text) onResult(res.text, res.detected_language, res.english_text);
    } catch {
      setError("Voice failed");
    } finally {
      setState("idle");
    }
  }

  if (error) {
    return (
      <button onClick={() => setError(null)} className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-500" title={error}>
        <Icons name="mic" className="h-4 w-4" />
      </button>
    );
  }

  return (
    <button
      onClick={state === "recording" ? stop : start}
      className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl transition-colors ${
        state === "recording"
          ? "animate-pulse bg-red-500 text-white"
          : state === "sending"
          ? "bg-slate-200 text-slate-400"
          : "bg-slate-100 text-slate-500 hover:bg-slate-200"
      }`}
      title={state === "recording" ? "Stop recording" : "Voice input"}
    >
      <Icons name="mic" className="h-4 w-4" />
    </button>
  );
}
