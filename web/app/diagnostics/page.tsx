"use client";

import { useState, useRef, useEffect } from "react";
import { useRequireAuth } from "@/lib/guards";
import { apiFetch } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { Spinner } from "@/components/ui";
import { Icons } from "@/components/icons";
import { DIELECTS, formatDateTime, getErrorMessage } from "@/lib/utils";

interface Diagnostic {
  id: number;
  crop_type: string;
  prediction: {
    label: string;
    healthy?: boolean;
    confidence?: number;
    advice?: string;
    plant_identification?: string;
    condition_summary?: string;
    root_cause_analysis?: string;
    severity?: string;
    affected_parts?: string[];
    spread_risk?: string;
    immediate_actions?: string[];
    long_term_management?: string[];
    local_products?: string[];
    references?: string[];
  };
  confidence: number;
  model: string;
  advice?: string | null;
  created_at: string;
}

interface VoiceAnswer {
  answer: string;
  translated?: string | null;
  tts_audio_url?: string | null;
  guardrail: boolean;
  dialect: string;
}

interface ChatHistoryEntry {
  id: number;
  role: string;
  content: string;
  language: string;
  created_at: string;
}

const QUICK_QUESTIONS = [
  "How do I plant maize?",
  "My coffee leaves have yellow spots",
  "When should I plant beans?",
  "How do I raise chickens?",
];

export default function DiagnosticsPage() {
  useRequireAuth();
  const history = useApi<Diagnostic[]>("/diagnostics");
  const chatHistory = useApi<ChatHistoryEntry[]>("/voice/history");

  const [locale, setLocale] = useState("en");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<Diagnostic | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [voiceText, setVoiceText] = useState("");
  const [conversation, setConversation] = useState<Array<{ user: string; assistant: string }>>([]);
  const [asking, setAsking] = useState(false);
  const conversationEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chatHistory.data && chatHistory.data.length > 0) {
      const entries: Array<{ user: string; assistant: string }> = [];
      for (let i = 0; i < chatHistory.data.length - 1; i++) {
        if (chatHistory.data[i].role === "user" && chatHistory.data[i + 1].role === "assistant") {
          entries.push({
            user: chatHistory.data[i].content,
            assistant: chatHistory.data[i + 1].content,
          });
          i++;
        }
      }
      setConversation(entries.slice(-10));
    }
  }, [chatHistory.data]);

  async function analyzeImage() {
    if (!image) return;
    setAnalyzing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", image);
      form.append("crop_type", "auto");
      const res = await apiFetch<Diagnostic>("/diagnostics/analyze", { method: "POST", formData: form });
      setResult(res);
      history.refetch();
      if (res.advice) {
        setConversation((prev) => [...prev.slice(-9), { user: "What's wrong with this plant?", assistant: res.advice || "I analyzed your photo." }]);
        setTimeout(() => conversationEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  }

  async function askQuestion(text: string, lang?: string, englishText?: string) {
    const q = text.trim();
    if (!q) return;
    setAsking(true);
    setError(null);
    setVoiceText("");
    try {
      const res = await apiFetch<VoiceAnswer>("/voice/chat", {
        method: "POST",
        body: {
          text: q,
          locale,
          crop_type: "general",
          detected_language: lang || locale,
          english_text: englishText || q,
        },
      });
      const displayText = res.translated || res.answer;
      setConversation((prev) => [...prev.slice(-9), { user: q, assistant: displayText }]);
      setTimeout(() => conversationEndRef.current?.scrollIntoView({ behavior: "smooth" }), 100);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAsking(false);
    }
  }

  function speak(text: string | undefined | null) {
    if (!text || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = locale === "lg" ? "lg" : locale === "sw" ? "sw" : "en-UG";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="animate-fade-in mx-auto max-w-2xl space-y-4">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-slate-900">NOVA Assistant</h1>
        <p className="text-sm text-slate-500">Ask anything about farming in Uganda</p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <VoiceRecorder onTranscript={(text, lang, eng) => askQuestion(text, lang, eng)} />
          <select value={locale} onChange={(e) => setLocale(e.target.value)} className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs">
            {DIELECTS.map((d) => (
              <option key={d.code} value={d.code}>{d.label}</option>
            ))}
          </select>
        </div>

        <div className="flex gap-2">
          <input
            value={voiceText}
            onChange={(e) => setVoiceText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !asking && askQuestion(voiceText)}
            placeholder="Type your question..."
            className={`${inputCls} flex-1`}
            disabled={asking}
          />
          <button
            onClick={() => askQuestion(voiceText)}
            disabled={asking || !voiceText.trim()}
            className="rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-700 disabled:opacity-50"
          >
            {asking ? "..." : "Ask"}
          </button>
        </div>

        {conversation.length === 0 && !asking && (
          <div className="mt-3 flex flex-wrap gap-2">
            {QUICK_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => askQuestion(q)}
                className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {error && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

        {conversation.length > 0 && (
          <div className="mt-4 max-h-[60vh] space-y-3 overflow-y-auto">
            {conversation.map((exchange, i) => (
              <div key={i} className="space-y-2">
                <div className="ml-8 rounded-2xl rounded-br-sm bg-blue-50 px-4 py-2.5 text-sm text-blue-900">
                  {exchange.user}
                </div>
                <div className="mr-8 rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-2.5 text-sm text-slate-800">
                  <div className="whitespace-pre-line">{exchange.assistant}</div>
                  <button
                    onClick={() => speak(exchange.assistant)}
                    className="mt-2 text-xs text-brand-600 hover:underline"
                  >
                    Listen
                  </button>
                </div>
              </div>
            ))}
            {asking && (
              <div className="mr-8 rounded-2xl rounded-bl-sm bg-slate-100 px-4 py-3 text-sm text-slate-400">
                <Spinner /> Thinking...
              </div>
            )}
            <div ref={conversationEndRef} />
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Icons name="scan" className="h-4 w-4 text-brand-600" /> Photo Diagnosis
        </h2>

        <div className="flex items-center gap-3">
          <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-600 hover:border-brand-400">
            <Icons name="camera" className="h-4 w-4" />
            {preview ? "Change photo" : "Upload a plant photo"}
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0] ?? null;
                setImage(file);
                setPreview(file ? URL.createObjectURL(file) : null);
                setResult(null);
              }}
            />
          </label>
          {preview && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={preview} alt="" className="h-12 w-12 rounded-lg object-cover" />
          )}
          <button
            onClick={analyzeImage}
            disabled={analyzing || !image}
            className="rounded-xl bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50"
          >
            {analyzing ? "Analyzing..." : "Check plant"}
          </button>
        </div>

        {result && result.advice && (
          <div className="mt-3 rounded-xl bg-brand-50 p-3 text-sm text-brand-900">
            <div className="whitespace-pre-line">{result.advice}</div>
            <p className="mt-2 text-xs text-brand-600">{formatDateTime(result.created_at)}</p>
          </div>
        )}
      </div>

      {history.data && history.data.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Recent</h2>
          <ul className="space-y-1">
            {history.data.slice(0, 5).map((d) => (
              <li key={d.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="capitalize text-slate-700">{d.prediction.label?.replace(/_/g, " ")}</span>
                <span className="text-xs text-slate-500">{formatDateTime(d.created_at)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
