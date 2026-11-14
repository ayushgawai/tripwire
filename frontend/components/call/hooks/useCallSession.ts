"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  applyWearerProtectionRouting,
  deriveUiStatus,
  restoreWearerAudioAfterExplicitReconnect,
} from "../audio/selectiveRouting";
import { createCallClient } from "../providers/MockCallClient";
import type {
  CallParticipant,
  CallProviderClient,
  CallSessionView,
  EventEnvelope,
  ProviderCredentials,
  Role,
  SessionState,
} from "../types";
import { useCallEvents } from "./useCallEvents";

export interface UseCallSessionArgs {
  sessionId: string;
  role: Role;
  /** Ayush opaque session token for this role (X-Session-Token). */
  accessToken: string;
  backendUrl: string;
  /** Pre-fetched join credentials from parent (Dev CallSurface). */
  initialCredentials?: ProviderCredentials | null;
  forceFixture?: boolean;
}

async function postJson<T>(
  url: string,
  body: unknown,
  accessToken: string
): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-Token": accessToken,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function useCallSession(args: UseCallSessionArgs) {
  const {
    sessionId,
    role,
    accessToken,
    backendUrl,
    initialCredentials = null,
    forceFixture,
  } = args;
  const clientRef = useRef<CallProviderClient | null>(null);
  const providerJoinSent = useRef(false);
  const familyJoinedSent = useRef(false);
  const [state, setState] = useState<SessionState>("monitoring");
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [participants, setParticipants] = useState<CallParticipant[]>([]);
  const [fixtureMode, setFixtureMode] = useState(true);
  const [callerAudioBlocked, setCallerAudioBlocked] = useState(false);
  const [wearerMicrophonePaused, setWearerMicPaused] = useState(false);
  const [workerReady, setWorkerReady] = useState(false);
  const [familyAlertSent, setFamilyAlertSent] = useState(false);
  const [familyJoined, setFamilyJoined] = useState(false);
  const [wearerProtected, setWearerProtected] = useState(false);
  const [wearerReconnected, setWearerReconnected] = useState(false);
  const [takeoverError, setTakeoverError] = useState<string | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<ProviderCredentials | null>(
    initialCredentials
  );
  const callerIdRef = useRef<string | null>(null);
  const routingSent = useRef(false);
  const protectingRef = useRef(false);

  const base = backendUrl.replace(/\/$/, "");

  const tryWearerRouting = useCallback(async () => {
    if (role !== "wearer" || !clientRef.current || routingSent.current) return;
    if (!protectingRef.current) return;
    const callerId =
      callerIdRef.current ||
      clientRef.current
        .getParticipants()
        .find((p) => p.role === "caller" && !p.local)?.id;
    if (!callerId) return;
    try {
      await applyWearerProtectionRouting({
        client: clientRef.current,
        sessionId,
        callerParticipantId: callerId,
      });
      routingSent.current = true;
      setCallerAudioBlocked(true);
      setWearerMicPaused(true);
      // Frozen contract: POST /signals { signal: "wearer_audio_blocked" }
      await postJson(
        `${base}/api/sessions/${sessionId}/signals`,
        { signal: "wearer_audio_blocked" },
        accessToken
      );
    } catch (err) {
      setTakeoverError(err instanceof Error ? err.message : "Routing failed");
    }
  }, [accessToken, base, role, sessionId]);

  const onEvent = useCallback(
    async (event: EventEnvelope) => {
      switch (event.type) {
        case "takeover.started":
          setState("protecting");
          protectingRef.current = true;
          setWearerProtected(true);
          setTakeoverError(null);
          setWorkerReady(false);
          await tryWearerRouting();
          break;
        case "takeover.active":
          setState("assistant_active");
          protectingRef.current = false;
          setWorkerReady(true);
          setCallerAudioBlocked(true);
          setWearerMicPaused(true);
          break;
        case "takeover.failed":
          setTakeoverError(
            String((event.payload as { reason?: string }).reason ?? "takeover_failed")
          );
          setWorkerReady(false);
          protectingRef.current = false;
          break;
        case "family.alert":
          setFamilyAlertSent(true);
          break;
        case "family.joined":
          setState("family_joined");
          setFamilyJoined(true);
          setWearerProtected(true);
          break;
        case "wearer.reconnected":
          setWearerReconnected(true);
          setWearerProtected(false);
          break;
        case "session.ended":
          setState("ended");
          await clientRef.current?.disconnect();
          setConnected(false);
          break;
        case "worker.ready":
          setWorkerReady(true);
          break;
        case "error":
          setProviderError(
            String((event.payload as { message?: string }).message ?? "error")
          );
          break;
        default:
          break;
      }
    },
    [tryWearerRouting]
  );

  const { events, connected: wsConnected, lastError: wsError } = useCallEvents({
    sessionId,
    backendUrl,
    accessToken,
    onEvent,
  });

  const connectWithCredentials = useCallback(
    async (creds: ProviderCredentials) => {
      if (clientRef.current) {
        await clientRef.current.destroy();
        clientRef.current = null;
      }
      providerJoinSent.current = false;
      familyJoinedSent.current = false;

      const client = createCallClient(
        forceFixture || creds.fixture_mode || creds.provider === "mock"
          ? "mock"
          : "daily"
      );
      clientRef.current = client;
      setFixtureMode(Boolean(creds.fixture_mode || forceFixture));
      setCredentials(creds);

      const unsubErr = client.onError((m) => setProviderError(m));
      const unsubJoin = client.onParticipantJoined((p) => {
        if (p.role === "caller") callerIdRef.current = p.id;
        setParticipants(client.getParticipants());
        if (protectingRef.current) {
          void tryWearerRouting();
        }
      });

      await client.connect(creds);
      setParticipants(client.getParticipants());
      const caller = client.getParticipants().find((p) => p.role === "caller");
      if (caller) callerIdRef.current = caller.id;

      const localId = client.getLocalParticipantId();
      if (localId && !providerJoinSent.current) {
        providerJoinSent.current = true;
        if (role === "family" && !familyJoinedSent.current) {
          familyJoinedSent.current = true;
          // Real provider join confirmation for Ayush mark_family_joined.
          // Host (app.py) should map this body to session.mark_family_joined + calls.stop_assistant.
          await fetch(`${base}/api/sessions/${sessionId}/family-joined`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Session-Token": accessToken,
            },
            body: JSON.stringify({
              role: "family",
              provider_participant_id: localId,
              user_id_from_provider: creds.user_id,
            }),
          }).catch(() => {
            /* ignore transient network errors; snapshot/WS recover state */
          });
        }
      }

      setConnected(true);
      if (protectingRef.current) {
        await tryWearerRouting();
      }
      return () => {
        unsubErr();
        unsubJoin();
      };
    },
    [accessToken, base, forceFixture, role, sessionId, tryWearerRouting]
  );

  const join = useCallback(async () => {
    setConnecting(true);
    setProviderError(null);
    try {
      const joinRes = await postJson<
        ProviderCredentials & {
          credentials?: ProviderCredentials;
          fixture_mode?: boolean;
          state?: SessionState;
        }
      >(
        `${base}/api/sessions/${sessionId}/join`,
        { role },
        accessToken
      );
      const creds =
        (joinRes.credentials as ProviderCredentials | undefined) ??
        (joinRes as ProviderCredentials);
      if (joinRes.state) setState(joinRes.state);
      await connectWithCredentials(creds);
    } catch (err) {
      setProviderError(err instanceof Error ? err.message : "Join failed");
      throw err;
    } finally {
      setConnecting(false);
    }
  }, [accessToken, base, connectWithCredentials, role, sessionId]);

  // Parent-supplied credentials (CallSurface) — connect once.
  useEffect(() => {
    if (!initialCredentials || connected || connecting) return;
    void (async () => {
      setConnecting(true);
      try {
        await connectWithCredentials(initialCredentials);
      } catch (err) {
        setProviderError(err instanceof Error ? err.message : "Connect failed");
      } finally {
        setConnecting(false);
      }
    })();
  }, [initialCredentials, connected, connecting, connectWithCredentials]);

  const endCall = useCallback(async () => {
    await postJson(`${base}/api/sessions/${sessionId}/end`, {}, accessToken);
    await clientRef.current?.destroy();
    clientRef.current = null;
    setConnected(false);
    setState("ended");
  }, [accessToken, base, sessionId]);

  const reconnectWearer = useCallback(async () => {
    // Contract: family/presenter sends wearer_reconnect in family_joined.
    await postJson(
      `${base}/api/sessions/${sessionId}/signals`,
      { signal: "wearer_reconnect" },
      accessToken
    );
    if (role === "wearer" && clientRef.current) {
      await restoreWearerAudioAfterExplicitReconnect(
        clientRef.current,
        callerIdRef.current
      );
      setCallerAudioBlocked(false);
      setWearerMicPaused(false);
      setWearerProtected(false);
      setWearerReconnected(true);
    }
  }, [accessToken, base, role, sessionId]);

  useEffect(() => {
    return () => {
      void clientRef.current?.destroy();
      clientRef.current = null;
    };
  }, []);

  const uiStatus = useMemo(
    () =>
      deriveUiStatus({
        state,
        connected,
        connecting,
        fixtureMode,
        familyAlertSent,
        takeoverFailed: Boolean(takeoverError),
        providerError,
      }),
    [
      state,
      connected,
      connecting,
      fixtureMode,
      familyAlertSent,
      takeoverError,
      providerError,
    ]
  );

  const view: CallSessionView = {
    sessionId,
    role,
    state,
    uiStatus,
    fixtureMode,
    participants,
    callerAudioBlocked,
    wearerMicrophonePaused,
    workerReady,
    familyAlertSent,
    familyJoined,
    wearerProtected,
    wearerReconnected,
    takeoverError,
    providerError: providerError || wsError,
    connected: connected && (wsConnected || fixtureMode),
  };

  return {
    view,
    events,
    credentials,
    join,
    endCall,
    reconnectWearer,
    connecting,
    clientRef,
  };
}
