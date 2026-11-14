"use client";
// One hook every page uses. Live mode: snapshot → WebSocket → reconnect (snapshot first).
// Replay mode (?replay=1): local fixtures, synced across tabs, visibly labeled.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, ApiError, wsUrl } from "./api.ts";
import { applyEvent, emptyView, viewFromSnapshot } from "./reducer.ts";
import { REPLAY_END, REPLAY_FAMILY_JOIN, REPLAY_RECONNECT, getScenario } from "./fixtures.ts";
import { ReplayBus } from "./replay.ts";
import type { EventEnvelope, JoinCredentials, Role, SessionView } from "./types.ts";

export type ConnectionStatus = "idle" | "connecting" | "live" | "reconnecting" | "offline" | "replay";

type Action =
  | { t: "event"; e: EventEnvelope }
  | { t: "snapshot"; v: SessionView }
  | { t: "reset"; id: string };

function reducer(state: SessionView, a: Action): SessionView {
  switch (a.t) {
    case "event":
      return applyEvent(state, a.e);
    case "snapshot":
      // Keep the local event log for the presenter's debug panel.
      return { ...a.v, log: state.log, seenEventIds: state.seenEventIds };
    case "reset":
      return emptyView(a.id);
  }
}

export interface SessionParams {
  sessionId: string;
  token: string | null;
  replay: boolean;
  scenario: string | null;
}

export function useSessionParams(): SessionParams {
  const sp = useSearchParams();
  const replayParam = sp.get("replay");
  const replay = replayParam !== null && replayParam !== "0" && replayParam !== "false";
  return {
    sessionId: sp.get("session") || (replay ? "replay_demo" : ""),
    token: sp.get("token"),
    replay,
    scenario: replay && replayParam && replayParam !== "1" && replayParam !== "true" ? replayParam : null,
  };
}

export function roleLink(role: string, p: Pick<SessionParams, "sessionId" | "token" | "replay">) {
  const q = new URLSearchParams();
  if (p.sessionId) q.set("session", p.sessionId);
  if (p.token) q.set("token", p.token);
  if (p.replay) q.set("replay", "1");
  return `/${role}?${q.toString()}`;
}

export function useSession(params: SessionParams) {
  const { sessionId, token, replay } = params;
  const [view, dispatch] = useReducer(reducer, sessionId, (id) => emptyView(id));
  const [status, setStatus] = useState<ConnectionStatus>(replay ? "replay" : "idle");
  const [lastError, setLastError] = useState<string | null>(null);
  const busRef = useRef<ReplayBus | null>(null);

  // ---- Replay mode -------------------------------------------------------
  useEffect(() => {
    if (!replay || !sessionId) return;
    dispatch({ t: "reset", id: sessionId });
    setStatus("replay");
    const bus = new ReplayBus(
      sessionId,
      (e) => dispatch({ t: "event", e }),
      () => dispatch({ t: "reset", id: sessionId }),
    );
    busRef.current = bus;
    return () => {
      bus.close();
      busRef.current = null;
    };
  }, [replay, sessionId]);

  // ---- Live mode ---------------------------------------------------------
  useEffect(() => {
    if (replay || !sessionId) return;
    let ws: WebSocket | null = null;
    let cancelled = false;
    let attempt = 0;
    let retry: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      if (cancelled) return;
      setStatus(attempt === 0 ? "connecting" : "reconnecting");
      // Reconnecting clients fetch the snapshot first (contract).
      try {
        const snap = await api.getSession(sessionId, token);
        if (cancelled) return;
        dispatch({ t: "snapshot", v: viewFromSnapshot(snap) });
        setLastError(null);
      } catch (err) {
        if (cancelled) return;
        setLastError(err instanceof Error ? err.message : String(err));
        if (err instanceof ApiError && (err.status === 401 || err.status === 403 || err.status === 404)) {
          setStatus("offline");
          return; // Don't hammer a session we can't access.
        }
        scheduleRetry();
        return;
      }
      try {
        ws = new WebSocket(wsUrl(sessionId, token));
      } catch (err) {
        setLastError(String(err));
        scheduleRetry();
        return;
      }
      ws.onopen = () => {
        attempt = 0;
        setStatus("live");
      };
      ws.onmessage = (m) => {
        try {
          const data = JSON.parse(String(m.data));
          const list: EventEnvelope[] = Array.isArray(data) ? data : [data];
          for (const e of list) if (e && e.type) dispatch({ t: "event", e });
        } catch {
          /* ignore non-JSON frames (keepalives) */
        }
      };
      ws.onclose = () => {
        if (!cancelled) scheduleRetry();
      };
      ws.onerror = () => ws?.close();
    };

    const scheduleRetry = () => {
      if (cancelled) return;
      attempt += 1;
      setStatus("reconnecting");
      const delay = Math.min(8000, 500 * 2 ** Math.min(attempt, 4));
      retry = setTimeout(connect, delay);
    };

    connect();
    return () => {
      cancelled = true;
      if (retry) clearTimeout(retry);
      if (ws) {
        ws.onclose = null;
        ws.close();
      }
    };
  }, [replay, sessionId, token]);

  // ---- Actions -----------------------------------------------------------
  const guard = useCallback(async <T,>(fn: () => Promise<T>): Promise<T | null> => {
    try {
      setLastError(null);
      return await fn();
    } catch (err) {
      setLastError(err instanceof Error ? err.message : String(err));
      return null;
    }
  }, []);

  const join = useCallback(
    async (role: Role): Promise<JoinCredentials | null> => {
      if (replay) {
        if (role === "family") busRef.current?.run(REPLAY_FAMILY_JOIN);
        return { replay: true };
      }
      return guard(() => api.join(sessionId, role, token));
    },
    [replay, sessionId, token, guard],
  );

  const end = useCallback(async () => {
    if (replay) return busRef.current?.run(REPLAY_END);
    await guard(() => api.end(sessionId, token));
  }, [replay, sessionId, token, guard]);

  const reconnectWearer = useCallback(async () => {
    if (replay) return busRef.current?.run(REPLAY_RECONNECT);
    await guard(() => api.reconnectWearer(sessionId, token));
  }, [replay, sessionId, token, guard]);

  const requestTakeover = useCallback(
    async (decisionId: string) => {
      if (replay) return;
      await guard(() => api.takeover(sessionId, decisionId, token));
    },
    [replay, sessionId, token, guard],
  );

  const runScenario = useCallback((id: string) => {
    const bus = busRef.current;
    if (!bus) return;
    bus.reset();
    bus.run(getScenario(id).steps);
  }, []);

  const resetReplay = useCallback(() => busRef.current?.reset(), []);

  return {
    view,
    status,
    lastError,
    replay,
    actions: { join, end, reconnectWearer, requestTakeover, runScenario, resetReplay },
  };
}

export type SessionHook = ReturnType<typeof useSession>;
