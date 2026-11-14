"use client";

import { useEffect, useRef, useState } from "react";
import type { EventEnvelope } from "../types";

export interface UseCallEventsOptions {
  sessionId: string;
  backendUrl: string;
  accessToken?: string;
  enabled?: boolean;
  onEvent?: (event: EventEnvelope) => void;
}

/**
 * WebSocket event stream with safe reconnect + snapshot-first recovery.
 * Contract: WS /ws/sessions/{id}?token= ; clients fetch GET snapshot first.
 */
export function useCallEvents(options: UseCallEventsOptions): {
  events: EventEnvelope[];
  connected: boolean;
  lastError: string | null;
  lastSequence: number;
} {
  const { sessionId, backendUrl, accessToken, enabled = true, onEvent } = options;
  const [events, setEvents] = useState<EventEnvelope[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastSequence, setLastSequence] = useState(0);
  const seen = useRef(new Set<string>());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled || !sessionId) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const ingest = (data: EventEnvelope) => {
      if (!data?.event_id || seen.current.has(data.event_id)) return;
      seen.current.add(data.event_id);
      setEvents((prev) => [...prev, data]);
      if (typeof data.sequence === "number") {
        setLastSequence((s) => Math.max(s, data.sequence));
      }
      onEventRef.current?.(data);
    };

    const fetchSnapshot = async () => {
      const base = backendUrl.replace(/\/$/, "");
      try {
        const res = await fetch(
          `${base}/api/sessions/${encodeURIComponent(sessionId)}`,
          {
            headers: accessToken
              ? { "X-Session-Token": accessToken }
              : undefined,
            cache: "no-store",
          }
        );
        if (!res.ok) return;
        const snap = (await res.json()) as {
          last_sequence?: number;
          state?: string;
        };
        if (typeof snap.last_sequence === "number") {
          setLastSequence(snap.last_sequence);
        }
      } catch {
        /* snapshot optional during fixture */
      }
    };

    const connect = () => {
      void fetchSnapshot();
      const base = backendUrl.replace(/\/$/, "");
      const q = accessToken ? `?token=${encodeURIComponent(accessToken)}` : "";
      const wsUrl =
        base.replace(/^http/, "ws") +
        `/ws/sessions/${encodeURIComponent(sessionId)}${q}`;
      try {
        ws = new WebSocket(wsUrl);
      } catch (err) {
        setLastError(err instanceof Error ? err.message : "WebSocket open failed");
        schedule();
        return;
      }
      ws.onopen = () => {
        if (cancelled) return;
        setConnected(true);
        setLastError(null);
        retry = 0;
      };
      ws.onmessage = (msg) => {
        if (cancelled) return;
        try {
          ingest(JSON.parse(String(msg.data)) as EventEnvelope);
        } catch {
          setLastError("Invalid event payload");
        }
      };
      ws.onerror = () => {
        setLastError("WebSocket error");
      };
      ws.onclose = () => {
        setConnected(false);
        if (!cancelled) schedule();
      };
    };

    const schedule = () => {
      const delay = Math.min(8000, 500 * 2 ** retry);
      retry += 1;
      timer = setTimeout(connect, delay);
    };

    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [sessionId, backendUrl, accessToken, enabled]);

  return { events, connected, lastError, lastSequence };
}
