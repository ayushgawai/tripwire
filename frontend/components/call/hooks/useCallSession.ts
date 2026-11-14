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
  accessToken: string;
  backendUrl: string;
  /** When true, prefer mock client even if credentials say daily. */
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
      "X-Tripwire-Access": accessToken,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export function useCallSession(args: UseCallSessionArgs) {
  const { sessionId, role, accessToken, backendUrl, forceFixture } = args;
  const clientRef = useRef<CallProviderClient | null>(null);
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
    null
  );
  const callerIdRef = useRef<string | null>(null);
  const routingSent = useRef(false);

  const onEvent = useCallback(
    async (event: EventEnvelope) => {
      switch (event.type) {
        case "takeover.started":
          setState("protecting");
          setWearerProtected(true);
          setTakeoverError(null);
          if (role === "wearer" && clientRef.current && !routingSent.current) {
            const callerId =
              callerIdRef.current ||
              clientRef.current
                .getParticipants()
                .find((p) => p.role === "caller" && !p.local)?.id;
            if (callerId) {
              try {
                const confirmation = await applyWearerProtectionRouting({
                  client: clientRef.current,
                  sessionId,
                  callerParticipantId: callerId,
                });
                routingSent.current = true;
                setCallerAudioBlocked(true);
                setWearerMicPaused(true);
                await postJson(
                  `${backendUrl.replace(/\/$/, "")}/api/sessions/${sessionId}/routing-confirmation`,
                  confirmation,
                  accessToken
                );
              } catch (err) {
                setTakeoverError(
                  err instanceof Error ? err.message : "Routing failed"
                );
              }
            }
          }
          break;
        case "takeover.active":
          setState("assistant_active");
          setWorkerReady(true);
          setCallerAudioBlocked(true);
          setWearerMicPaused(true);
          break;
        case "takeover.failed":
          setTakeoverError(
            String((event.payload as { reason?: string }).reason ?? "takeover_failed")
          );
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
    [accessToken, backendUrl, role, sessionId]
  );

  const { events, connected: wsConnected, lastError: wsError } = useCallEvents({
    sessionId,
    backendUrl,
    onEvent,
  });

  const join = useCallback(async () => {
    setConnecting(true);
    setProviderError(null);
    try {
      const base = backendUrl.replace(/\/$/, "");
      const joinRes = await postJson<{
        credentials: ProviderCredentials;
        fixture_mode?: boolean;
        state?: SessionState;
      }>(
        `${base}/api/sessions/${sessionId}/join`,
        { role, access_token: accessToken },
        accessToken
      );
      const creds = joinRes.credentials;
      setCredentials(creds);
      setFixtureMode(Boolean(creds.fixture_mode || forceFixture));
      if (joinRes.state) setState(joinRes.state);

      const client = createCallClient(
        forceFixture || creds.fixture_mode || creds.provider === "mock"
          ? "mock"
          : "daily"
      );
      clientRef.current = client;
      const unsubErr = client.onError((m) => setProviderError(m));
      const unsubJoin = client.onParticipantJoined((p) => {
        if (p.role === "caller") callerIdRef.current = p.id;
        setParticipants(client.getParticipants());
        if (role === "family" || role === "caller" || role === "wearer") {
          void postJson(
            `${base}/api/sessions/${sessionId}/provider-join`,
            {
              role,
              access_token: accessToken,
              provider_participant_id: client.getLocalParticipantId(),
            },
            accessToken
          ).catch(() => {
            /* Ayush may not have route yet — adapter reports in CAPABILITIES */
          });
        }
        if (role === "family" && p.local) {
          void postJson(
            `${base}/api/sessions/${sessionId}/family-joined`,
            {
              access_token: accessToken,
              provider_participant_id: p.id,
              user_id_from_provider: creds.user_id,
            },
            accessToken
          );
        }
      });
      await client.connect(creds);
      setParticipants(client.getParticipants());
      const caller = client.getParticipants().find((p) => p.role === "caller");
      if (caller) callerIdRef.current = caller.id;
      setConnected(true);
      return () => {
        unsubErr();
        unsubJoin();
      };
    } catch (err) {
      setProviderError(err instanceof Error ? err.message : "Join failed");
      throw err;
    } finally {
      setConnecting(false);
    }
  }, [accessToken, backendUrl, forceFixture, role, sessionId]);

  const endCall = useCallback(async () => {
    const base = backendUrl.replace(/\/$/, "");
    await postJson(`${base}/api/sessions/${sessionId}/end`, {}, accessToken);
    await clientRef.current?.destroy();
    clientRef.current = null;
    setConnected(false);
    setState("ended");
  }, [accessToken, backendUrl, sessionId]);

  const reconnectWearer = useCallback(async () => {
    if (role !== "wearer") return;
    const base = backendUrl.replace(/\/$/, "");
    await postJson(
      `${base}/api/sessions/${sessionId}/reconnect-wearer`,
      { access_token: accessToken },
      accessToken
    );
    if (clientRef.current) {
      await restoreWearerAudioAfterExplicitReconnect(
        clientRef.current,
        callerIdRef.current
      );
      setCallerAudioBlocked(false);
      setWearerMicPaused(false);
      setWearerProtected(false);
      setWearerReconnected(true);
    }
  }, [accessToken, backendUrl, role, sessionId]);

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
    clientRef,
  };
}
