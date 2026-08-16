"use client";

import { useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Icons } from "@/components/icons";

type Status = "idle" | "recording" | "transcribing";

interface TranscribeResult {
  text: string;
  detected_language: string;
  english_text: string;
  needs_translation: boolean;
}

export function VoiceRecorder({
  onTranscript,
}: {
  onTranscript: (text: string, lang?: string, englishText?: string) => void;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [langInfo, setLangInfo] = useState<string | null>(null);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  async function start() {
    setError(null);
    setLangInfo(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 16000 },
      });
      const rec = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      mediaRef.current = rec;
      chunksRef.current = [];
      rec.ondataavailable = (e) => chunksRef.current.push(e.data);
      rec.onstop = send;
      rec.start();
      setStatus("recording");
    } catch {
      setError("Microphone access denied. Type your question instead.");
      setStatus("idle");
    }
  }

  function stop() {
    mediaRef.current?.stop();
    mediaRef.current?.stream.getTracks().forEach((t) => t.stop());
    setStatus("idle");
  }

  async function send() {
    if (!chunksRef.current.length) return;
    setStatus("transcribing");
    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    const form = new FormData();
    form.append("file", blob, "voice.webm");
    try {
      const res = await apiFetch<TranscribeResult>("/voice/transcribe", {
        method: "POST",
        formData: form,
      });
      if (res.text) {
        const langNames: Record<string, string> = {
          en: "English", lg: "Luganda", sw: "Swahili", ach: "Acholi",
          nyn: "Runyankore", rn: "Kirundi", sa: "Soga",
        };
        if (res.detected_language && res.detected_language !== "en") {
          setLangInfo(`Detected: ${langNames[res.detected_language] || res.detected_language}`);
        } else {
          setLangInfo(null);
        }
        onTranscript(res.text, res.detected_language, res.english_text);
      } else {
        setError("Could not transcribe. Type your question below.");
      }
    } catch {
      setError("Speech service unavailable. Type your question below.");
    } finally {
      setStatus("idle");
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={status === "recording" ? stop : start}
        className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-colors ${
          status === "recording" ? "animate-pulse bg-red-500 hover:bg-red-600" : "bg-ink-900 hover:bg-ink-700"
        }`}
      >
        <Icons name="mic" className="h-4 w-4" />
        {status === "recording" ? "Stop" : "Ask by voice"}
      </button>
      {status === "transcribing" && <span className="text-sm text-slate-500">Listening...</span>}
      {langInfo && <span className="text-xs text-brand-600 font-medium">{langInfo}</span>}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
