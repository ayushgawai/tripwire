"use client";

import { useEffect, useRef, useState } from "react";
import type { EventEnvelope } from "../types";

export interface UseCallEventsOptions {
  sessionId: string;
  backendUrl: string;
  enabled?: boolean;
  onEvent?: (event: EventEnvelope) => void;
}

/**
 * WebSocket event stream with safe reconnect.
 * Clients should fetch GET snapshot before relying on live events (Ayush contract).
 */
export function useCallEvents(options: UseCallEventsOptions): {
  events: EventEnvelope[];
  connected: boolean;
  lastError: string | null;
} {
  const { sessionId, backendUrl, enabled = true, onEvent } = options;
  const [events, setEvents] = useState<EventEnvelope[]>([]);
  const [connected, setConnected] = useState(false);
  const [lastError, setLastError] = useState<string | null>(null);
  const seen = useRef(new Set<string>());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  useEffect(() => {
    if (!enabled || !sessionId) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      const base = backendUrl.replace(/\/$/, "");
      const wsUrl =
        base.replace(/^http/, "ws") + `/ws/sessions/${encodeURIComponent(sessionId)}`;
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
          const data = JSON.parse(String(msg.data)) as EventEnvelope;
          if (!data?.event_id || seen.current.has(data.event_id)) return;
          seen.current.add(data.event_id);
          setEvents((prev) => [...prev, data]);
          onEventRef.current?.(data);
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
  }, [sessionId, backendUrl, enabled]);

  return { events, connected, lastError };
}
