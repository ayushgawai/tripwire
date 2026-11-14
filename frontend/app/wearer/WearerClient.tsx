"use client";
// The wearer sees a calm, plain-language scene. During protection, never the caller's words.
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useSession, useSessionParams } from "@/app/_lib/useSession";
import { useLiveTranscription } from "@/app/_lib/useLiveTranscription";
import { Button } from "@/components/ui/Button";
import { CallSurface } from "@/components/ui/CallSurface";
import { cn } from "@/components/ui/cn";
import { ConnectionBadge } from "@/components/ui/ConnectionBadge";
import { ErrorToast } from "@/components/ui/ErrorToast";
import { Logo } from "@/components/ui/Logo";
import { NoSession } from "@/components/ui/NoSession";
import { Pulse } from "@/components/ui/Pulse";
import { ReplayRibbon } from "@/components/ui/ReplayRibbon";
import type { JoinCredentials, Role, SessionView } from "@/app/_lib/types";

type Scene = {
  key: string;
  tone: "safe" | "watch" | "danger" | "family" | "muted";
  bg: string;
  icon: "shield" | "pause" | "alert" | "heart" | "check";
  title: string;
  body: string;
};

/** The wearer sees a calm, plain-language scene. During protection, never the caller's words. */
function sceneFor(v: SessionView, familyName: string): Scene {
  if (v.state === "ended")
    return { key: "ended", tone: "muted", bg: "bg-paper", icon: "check", title: "Call ended", body: "You're all set. Nothing else is needed from you." };
  if (v.takeover === "failed" && v.state !== "family_joined")
    return {
      key: "failed", tone: "danger", bg: "bg-danger-soft", icon: "alert",
      title: "Please hang up",
      body: `We couldn't pause this call automatically. Hanging up is safest. ${cap(familyName)} has been alerted.`,
    };
  switch (v.state) {
    case "protecting":
      return { key: "protecting", tone: "watch", bg: "bg-watch-soft", icon: "pause", title: "One moment…", body: "Tripwire is pausing this call so someone you trust can check it." };
    case "assistant_active":
      return {
        key: "assistant", tone: "danger", bg: "bg-danger-soft", icon: "alert",
        title: "This request may be unsafe",
        body: `We are asking ${familyName} to help. You don't need to say or do anything. Please don't send money or gift cards.`,
      };
    case "family_joined":
      return v.wearerReconnected
        ? { key: "reconnected", tone: "family", bg: "bg-family-soft", icon: "heart", title: `You're back with ${familyName}`, body: `${cap(familyName)} is on the call with you now.` }
        : { key: "family", tone: "family", bg: "bg-family-soft", icon: "heart", title: `${cap(familyName)} is here`, body: `${cap(familyName)} is talking to the caller. They'll bring you back in when it's safe.` };
    default:
      return v.alert
        ? { key: "alerted", tone: "watch", bg: "bg-watch-soft", icon: "shield", title: "Protection is on", body: `Something sounded unusual, so ${familyName} has been told. Take your time.` }
        : { key: "monitoring", tone: "safe", bg: "bg-safe-soft", icon: "shield", title: "Protection is on", body: "Tripwire is listening for risky requests on this call." };
  }
}

const ICON_COLOR = { safe: "text-safe", watch: "text-watch", danger: "text-danger", family: "text-family", muted: "text-ink-faint" };

function SceneIcon({ icon, tone }: { icon: Scene["icon"]; tone: Scene["tone"] }) {
  const common = "h-14 w-14";
  return (
    <span className={cn("relative flex h-28 w-28 items-center justify-center rounded-full bg-card shadow-sm", ICON_COLOR[tone])}>
      {tone !== "muted" && <span className="absolute inset-0 rounded-full bg-current opacity-20 animate-pulse-ring" />}
      <svg viewBox="0 0 24 24" className={common} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {icon === "shield" && (<><path d="M12 3l7 3v5c0 4.5-3 8.4-7 10-4-1.6-7-5.5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" /></>)}
        {icon === "pause" && (<><circle cx="12" cy="12" r="9" /><path d="M10 9v6M14 9v6" /></>)}
        {icon === "alert" && (<><path d="M12 3l9.5 17h-19L12 3z" /><path d="M12 10v4M12 17.5v.01" /></>)}
        {icon === "heart" && <path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z" />}
        {icon === "check" && (<><circle cx="12" cy="12" r="9" /><path d="M8 12l3 3 5-6" /></>)}
      </svg>
    </span>
  );
}

export default function WearerClient() {
  const params = useSessionParams();
  const { view, status, lastError, actions } = useSession(params);
  const [confirmEnd, setConfirmEnd] = useState(false);
  const familyName = useFamilyName();
  const tokenFromUrl = params.token;

  if (!params.sessionId) return <NoSession role="wearer" />;
  const scene = sceneFor(view, familyName);
  const protectedMode = view.state === "protecting" || view.state === "assistant_active" || (view.state === "family_joined" && !view.wearerReconnected);
  const callerMuted = view.takeover === "active" && protectedMode;
  // wearer_connected is false from protecting onward until family sends wearer_reconnect
  const wearerConnected = view.wearerReconnected || view.state === "monitoring";
  const ended = view.state === "ended";

  // ---- Live transcription ----
  const transcription = useLiveTranscription({
    sessionId: params.sessionId,
    token: tokenFromUrl,
    role: "wearer",
    enabled: !ended && !params.replay,
  });

  // Pause audio capture when wearer is disconnected (during protection / before reconnect)
  useEffect(() => {
    if (wearerConnected) return;
    transcription.stop();
  }, [wearerConnected, transcription.stop]);

  // Wrap onJoin to also start transcription after the user's join gesture
  const handleJoin = useCallback(async (role: Role): Promise<JoinCredentials | null> => {
    const result = await actions.join(role);
    if (result && wearerConnected) transcription.start();
    return result;
  }, [actions.join, wearerConnected, transcription.start]);

  return (
    <div className={cn("min-h-screen transition-colors duration-700", scene.bg)}>
      {(params.replay || view.demoReplay) && <ReplayRibbon />}
      <header className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
        <Logo />
        <ConnectionBadge status={status} />
      </header>

      <main className="mx-auto flex max-w-3xl flex-col items-center px-6 pb-16 pt-6 text-center">
        <div key={scene.key} className={cn("flex flex-col items-center gap-8 animate-rise", scene.key === "assistant" && "[&>span]:animate-shake")}>
          <SceneIcon icon={scene.icon} tone={scene.tone} />
          <div className="space-y-4">
            <h1 className="font-display text-5xl font-semibold leading-tight tracking-tight sm:text-6xl">{scene.title}</h1>
            <p className="mx-auto max-w-xl text-2xl leading-relaxed text-ink-soft">{scene.body}</p>
          </div>
        </div>

        {/* Audio status */}
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <StatusChip on={!callerMuted} tone={callerMuted ? "danger" : "safe"} label={callerMuted ? "Caller audio paused" : "Caller audio on"} />
          {!wearerConnected && !ended && (
            <StatusChip on={false} tone="danger" label="Your microphone is paused while family verifies" />
          )}
          {view.alert && (
            <StatusChip on tone="family" label={view.familyJoined ? `${cap(familyName)} joined` : `${cap(familyName)} alerted`} />
          )}
          {view.state === "assistant_active" && <StatusChip on tone="watch" label="Tripwire assistant speaking to caller" />}
        </div>

        <div className="mt-10 w-full max-w-xl">
          <CallSurface
            role="wearer"
            state={view.state}
            onJoin={handleJoin}
            replay={params.replay}
            sessionId={params.sessionId}
            accessToken={params.token}
          />
        </div>

        {/* Live captions strip */}
        {!ended && <LiveCaptionsStrip transcription={transcription} wearerConnected={wearerConnected} />}

        {!ended && (
          <div className="mt-8">
            {confirmEnd || scene.key === "failed" ? (
              <div className="flex flex-col items-center gap-3">
                <Button variant="danger" size="xl" onClick={() => { void actions.end(); setConfirmEnd(false); }}>
                  End call now
                </Button>
                {scene.key !== "failed" && (
                  <button className="text-lg text-ink-soft underline" onClick={() => setConfirmEnd(false)}>Keep the call</button>
                )}
              </div>
            ) : (
              <Button variant="outline" size="lg" onClick={() => setConfirmEnd(true)}>
                End call
              </Button>
            )}
          </div>
        )}
      </main>
      <ErrorToast message={lastError} />
    </div>
  );
}

function StatusChip({ on, tone, label }: { on: boolean; tone: "safe" | "danger" | "family" | "watch"; label: string }) {
  return (
    <span className="inline-flex items-center gap-2.5 rounded-full border border-line bg-card px-4 py-2 text-lg font-medium text-ink">
      <Pulse tone={tone} still={!on} size={10} />
      {label}
    </span>
  );
}

function useFamilyName() {
  return useSearchParams().get("family") || "your daughter";
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// ---- Live captions strip ----

function LiveCaptionsStrip({ transcription, wearerConnected }: { transcription: ReturnType<typeof useLiveTranscription>; wearerConnected: boolean }) {
  const { status, interim, lastFinal, error, start, stop } = transcription;
  const live = status === "live";

  return (
    <div className="w-full rounded-xl border border-line bg-card/80 p-3 text-left">
      <div className="flex items-center gap-2">
        <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", live ? "bg-safe animate-pulse" : status === "error" ? "bg-danger" : "bg-ink-faint")} />
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft">Live captions</span>
        <span className="ml-auto text-[10px] text-ink-faint capitalize">{status}</span>
        {live ? (
          <Button size="sm" variant="outline" onClick={stop}>Stop</Button>
        ) : (
          <Button size="sm" onClick={start} disabled={status === "starting" || !wearerConnected}>Start</Button>
        )}
      </div>
      {!wearerConnected && status !== "idle" && (
        <p className="mt-2 text-xs text-watch">Your microphone is paused while family verifies</p>
      )}
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
      {lastFinal && <p className="mt-2 text-sm text-ink">{lastFinal}</p>}
      {interim && <p className="mt-1 text-sm text-ink-faint italic">{interim}</p>}
      {!lastFinal && !interim && !error && <p className="mt-2 text-xs text-ink-faint">Press Start to begin live captions.</p>}
    </div>
  );
}
