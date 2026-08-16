"use client";

import { useState } from "react";
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
  prediction: { label: string; healthy?: boolean; confidence?: number; advice?: string };
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

export default function DiagnosticsPage() {
  useRequireAuth();
  const history = useApi<Diagnostic[]>("/diagnostics");

  const [cropType, setCropType] = useState("coffee");
  const [locale, setLocale] = useState("en");
  const [note, setNote] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<Diagnostic | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [voiceText, setVoiceText] = useState("");
  const [voiceAnswer, setVoiceAnswer] = useState<VoiceAnswer | null>(null);
  const [asking, setAsking] = useState(false);

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!image) return;
    setAnalyzing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", image);
      form.append("crop_type", cropType);
      if (note) form.append("note", note);
      form.append("locale", locale);
      const res = await apiFetch<Diagnostic>("/diagnostics/analyze", { method: "POST", formData: form });
      setResult(res);
      history.refetch();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  }

  async function askQuestion(text: string) {
    const q = text.trim();
    if (!q) return;
    setAsking(true);
    setError(null);
    try {
      const res = await apiFetch<VoiceAnswer>("/voice/query", {
        method: "POST",
        body: { text: q, locale, crop_type: cropType },
      });
      setVoiceAnswer(res);
      setVoiceText("");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAsking(false);
    }
  }

  function speak(text: string | undefined | null) {
    if (!text || !("speechSynthesis" in window)) return;
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = { lg: "lg", sw: "sw", ach: "ach", nyn: "nyn", en: "en-UG" }[locale] ?? "en-UG";
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  }

  const inputCls =
    "w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

  return (
    <div className="animate-fade-in space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Agribusiness AI assistant</h1>
        <p className="text-sm text-slate-500">
          Vision plant diagnostics + localized voice support. Guarded to agriculture topics only.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4">
          <form onSubmit={analyze} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
              <Icons name="scan" className="h-4 w-4 text-brand-600" /> Photo diagnosis
            </h2>

            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center hover:border-brand-400">
              {preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview} alt="preview" className="max-h-40 rounded-xl object-cover" />
              ) : (
                <>
                  <Icons name="camera" className="h-8 w-8 text-slate-400" />
                  <span className="text-sm font-medium text-slate-600">Upload a leaf or animal photo</span>
                  <span className="text-xs text-slate-400">JPG, PNG or WebP · max 8 MB</span>
                </>
              )}
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  setImage(file);
                  setPreview(file ? URL.createObjectURL(file) : null);
                }}
              />
            </label>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Subject</span>
                <select value={cropType} onChange={(e) => setCropType(e.target.value)} className={inputCls}>
                  <option value="coffee">Coffee</option>
                  <option value="livestock">Livestock</option>
                  <option value="grains">Grains</option>
                  <option value="produce">Produce</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">Advice language</span>
                <select value={locale} onChange={(e) => setLocale(e.target.value)} className={inputCls}>
                  {DIELECTS.map((d) => (
                    <option key={d.code} value={d.code}>{d.label}</option>
                  ))}
                </select>
              </label>
            </div>
            <label className="mt-3 block">
              <span className="mb-1 block text-sm font-medium text-slate-700">Notes for the model (optional)</span>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
                className={inputCls} placeholder="e.g. Leaves turning yellow near the base" />
            </label>

            {error && <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

            <button type="submit" disabled={analyzing || !image}
              className="mt-4 w-full rounded-xl bg-brand-500 py-2.5 text-sm font-semibold text-white hover:bg-brand-600 disabled:opacity-50">
              {analyzing ? "Analyzing…" : "Analyze image"}
            </button>
          </form>

          {result && (
            <div className="animate-fade-in rounded-2xl border border-brand-200 bg-brand-50 p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-brand-900">Diagnosis result</h3>
                <span className="text-xs text-brand-600">{result.model}</span>
              </div>
              <p className="mt-2 text-lg font-bold capitalize text-slate-900">
                {result.prediction.label?.replace(/_/g, " ")}
                <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-xs font-semibold text-brand-700">
                  {Math.round((result.prediction.confidence ?? result.confidence) * 100)}% confidence
                </span>
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-brand-100">
                <div className="h-full rounded-full bg-brand-500" style={{ width: `${(result.prediction.confidence ?? result.confidence) * 100}%` }} />
              </div>
              {result.advice && <p className="mt-3 text-sm text-brand-800">{result.advice}</p>}
              <p className="mt-2 text-xs text-brand-600">{formatDateTime(result.created_at)}</p>
            </div>
          )}
        </section>

        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
              <Icons name="mic" className="h-4 w-4 text-brand-600" /> Voice assistant
            </h2>
            <div className="flex flex-wrap items-center gap-3">
              <VoiceRecorder onTranscript={(text) => askQuestion(text)} />
              <select value={locale} onChange={(e) => setLocale(e.target.value)} className={inputCls}>
                {DIELECTS.map((d) => (
                  <option key={d.code} value={d.code}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="mt-3 flex gap-2">
              <input
                value={voiceText}
                onChange={(e) => setVoiceText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askQuestion(voiceText)}
                placeholder="Or type a question: how do I treat coffee leaf rust?"
                className={`${inputCls} flex-1`}
              />
              <button onClick={() => askQuestion(voiceText)} disabled={asking}
                className="rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-700 disabled:opacity-50">
                Ask
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-400">
              Guarded assistant — questions outside farming, coffee, livestock or food safety are declined.
            </p>

            {voiceAnswer && (
              <div className="animate-fade-in mt-4 rounded-2xl bg-slate-50 p-4">
                {!voiceAnswer.guardrail && (
                  <p className="flex items-center gap-2 text-sm font-semibold text-red-600">
                    <Icons name="alert" className="h-4 w-4" /> Out of domain
                  </p>
                )}
                <p className="mt-1 text-sm text-slate-700">{voiceAnswer.answer}</p>
                {voiceAnswer.translated && (
                  <p className="mt-2 border-t border-slate-200 pt-2 text-sm font-medium text-brand-700">
                    {voiceAnswer.translated}
                  </p>
                )}
                <button onClick={() => speak(voiceAnswer.translated ?? voiceAnswer.answer)}
                  className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-600">
                  <Icons name="mic" className="h-3.5 w-3.5" /> Play answer
                </button>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="mb-3 flex items-center gap-2 font-semibold text-slate-900">
              <Icons name="spark" className="h-4 w-4 text-brand-600" /> Recent diagnoses
            </h2>
            {history.loading ? (
              <Spinner />
            ) : history.data?.length ? (
              <ul className="space-y-2">
                {history.data.map((d) => (
                  <li key={d.id} className="flex items-center justify-between rounded-xl bg-slate-50 px-3 py-2 text-sm">
                    <div>
                      <p className="font-semibold capitalize text-slate-800">{d.prediction.label?.replace(/_/g, " ")}</p>
                      <p className="text-xs text-slate-500">{d.crop_type} · {formatDateTime(d.created_at)}</p>
                    </div>
                    <span className="text-xs font-bold text-brand-600">{Math.round(d.confidence * 100)}%</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500">No diagnoses yet — upload a photo above.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
