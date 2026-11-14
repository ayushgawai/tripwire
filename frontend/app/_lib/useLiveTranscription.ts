"use client";
// Live transcription via MediaRecorder + WebSocket STT endpoint.
// Contract: WS ${BACKEND}/ws/sessions/{id}/stt?token=<role token>&role=<caller|wearer>
//   Client → binary audio chunks (webm/opus)
//   Server → JSON {type:"interim"|"final"|"error", text|message}
import { useCallback, useEffect, useRef, useState } from "react";

export type TranscriptionStatus = "idle" | "starting" | "live" | "error";

export interface UseLiveTranscriptionOptions {
  sessionId: string;
  token: string | null;
  role: "caller" | "wearer";
  enabled?: boolean;
}

export interface UseLiveTranscriptionReturn {
  status: TranscriptionStatus;
  interim: string;
  lastFinal: string;
  error: string | null;
  start: () => void;
  stop: () => void;
}

const MIME_TYPE = "audio/webm;codecs=opus";
const FALLBACK_MIME = "audio/webm";
const CHUNK_INTERVAL_MS = 250;

function pickMimeType(): string {
  if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(MIME_TYPE)) return MIME_TYPE;
  if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(FALLBACK_MIME)) return FALLBACK_MIME;
  return "";
}

function buildWsUrl(base: string, sessionId: string, token: string | null, role: string): string {
  const url = new URL(base);
  // strip any existing path — wsUrl from api.ts already includes /ws/sessions/{id}?token=...
  // We need to append /stt?role=... instead.
  const wsBase = base.split("/ws/sessions/")[0];
  const tokenParam = token ? `?token=${encodeURIComponent(token)}&role=${encodeURIComponent(role)}` : `?role=${encodeURIComponent(role)}`;
  return `${wsBase}/ws/sessions/${encodeURIComponent(sessionId)}/stt${tokenParam}`;
}

export function useLiveTranscription({
  sessionId,
  token,
  role,
  enabled = true,
}: UseLiveTranscriptionOptions): UseLiveTranscriptionReturn {
  const [status, setStatus] = useState<TranscriptionStatus>("idle");
  const [interim, setInterim] = useState("");
  const [lastFinal, setLastFinal] = useState("");
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunkTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bufferRef = useRef<Blob[]>([]);
  const startedRef = useRef(false);
  const mountedRef = useRef(true);

  const cleanup = useCallback(() => {
    if (chunkTimerRef.current) { clearInterval(chunkTimerRef.current); chunkTimerRef.current = null; }
    try { recorderRef.current?.stop(); } catch { /* already stopped */ }
    recorderRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close();
    }
    wsRef.current = null;
    bufferRef.current = [];
  }, []);

  const stop = useCallback(() => {
    startedRef.current = false;
    cleanup();
    if (mountedRef.current) setStatus("idle");
  }, [cleanup]);

  const start = useCallback(async () => {
    if (!enabled || !sessionId) return;
    if (startedRef.current) return;
    startedRef.current = true;
    mountedRef.current = true;
    setError(null);
    setInterim("");
    setLastFinal("");
    setStatus("starting");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const wsBase = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");
      const wsUrl = buildWsUrl(wsBase, sessionId, token, role);
      const ws = new WebSocket(wsUrl);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;

      const mimeType = pickMimeType();

      ws.onopen = () => {
        if (!mountedRef.current) return;
        setStatus("live");
        try {
          const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
          recorder.ondataavailable = (e) => {
            if (e.data.size > 0) bufferRef.current.push(e.data);
          };
          recorder.start(CHUNK_INTERVAL_MS);
          recorderRef.current = recorder;

          // Flush accumulated chunks to the WS
          chunkTimerRef.current = setInterval(() => {
            const ws2 = wsRef.current;
            if (!ws2 || ws2.readyState !== WebSocket.OPEN || bufferRef.current.length === 0) return;
            const batch = bufferRef.current;
            bufferRef.current = [];
            // Send each blob individually as binary
            for (const blob of batch) {
              blob.arrayBuffer().then((ab) => ws2.send(ab)).catch(() => {});
            }
          }, CHUNK_INTERVAL_MS);
        } catch {
          // MediaRecorder failed — still keep WS open
          if (mountedRef.current) setError("Audio recording not supported in this browser.");
        }
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(typeof ev.data === "string" ? ev.data : "");
          if (data && typeof data.type === "string") {
            const text = typeof data.text === "string" ? data.text : "";
            if (data.type === "interim") {
              if (mountedRef.current) setInterim(text);
            } else if (data.type === "final") {
              if (mountedRef.current) {
                setLastFinal(text);
                setInterim("");
              }
            } else if (data.type === "error") {
              const msg = typeof data.message === "string" ? data.message : "STT error";
              if (mountedRef.current) setError(msg);
            }
          }
        } catch {
          // ignore non-JSON
        }
      };

      ws.onerror = () => {
        if (mountedRef.current) {
          setError("Transcription connection failed. Please retry.");
          setStatus("error");
        }
        startedRef.current = false;
      };

      ws.onclose = () => {
        startedRef.current = false;
        cleanup();
      };
    } catch (err) {
      startedRef.current = false;
      cleanup();
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        if (mountedRef.current) {
          setError("Microphone blocked. Allow mic access in the browser address bar, then retry.");
          setStatus("error");
        }
      } else if (err instanceof Error) {
        if (mountedRef.current) {
          setError(err.message);
          setStatus("error");
        }
      }
    }
  }, [enabled, sessionId, token, role, cleanup]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cleanup();
    };
  }, [cleanup]);

  return { status, interim, lastFinal, error, start, stop };
}
