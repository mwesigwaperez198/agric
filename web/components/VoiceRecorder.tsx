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

function getSupportedMimeType(): string {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
    "audio/wav",
  ];
  for (const type of types) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "";
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

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setError("Voice not supported on this device. Type your question below.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000,
        },
      });

      const mimeType = getSupportedMimeType();
      const options = mimeType ? { mimeType } : undefined;
      const rec = new MediaRecorder(stream, options);

      mediaRef.current = rec;
      chunksRef.current = [];

      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = send;
      rec.start();
      setStatus("recording");

      setTimeout(() => {
        if (rec.state === "recording") {
          rec.stop();
        }
      }, 30000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      if (msg.includes("NotAllowedError") || msg.includes("Permission")) {
        setError("Microphone blocked. Go to Settings > Microphone and allow access.");
      } else if (msg.includes("NotFoundError")) {
        setError("No microphone found. Type your question below.");
      } else {
        setError("Could not start recording. Type your question below.");
      }
      setStatus("idle");
    }
  }

  function stop() {
    if (mediaRef.current && mediaRef.current.state === "recording") {
      mediaRef.current.stop();
      mediaRef.current.stream.getTracks().forEach((t) => t.stop());
    }
    setStatus("idle");
  }

  async function send() {
    if (!chunksRef.current.length) return;
    setStatus("transcribing");

    const mimeType = chunksRef.current[0]?.type || "audio/webm";
    const blob = new Blob(chunksRef.current, { type: mimeType });
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
          setLangInfo(`${langNames[res.detected_language] || res.detected_language} detected`);
        } else {
          setLangInfo(null);
        }
        onTranscript(res.text, res.detected_language, res.english_text);
      } else {
        setError("Could not understand. Please type your question.");
      }
    } catch {
      setError("Voice service unavailable. Type your question.");
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
        {status === "recording" ? "Stop" : "Speak"}
      </button>
      {status === "transcribing" && <span className="text-sm text-slate-500">Listening...</span>}
      {langInfo && <span className="text-xs text-brand-600 font-medium">{langInfo}</span>}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}
