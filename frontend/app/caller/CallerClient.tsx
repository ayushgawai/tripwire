"use client";
// The caller sees an ordinary calling screen. No risk scores, no evidence — only what they would
// legitimately hear: the Tripwire assistant identifies itself, and later a family member joins.
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useSession, useSessionParams } from "@/app/_lib/useSession";
import { useLiveTranscription } from "@/app/_lib/useLiveTranscription";
import { Button } from "@/components/ui/Button";
import { CallSurface } from "@/components/ui/CallSurface";
import { cn } from "@/components/ui/cn";
import { ConnectionBadge } from "@/components/ui/ConnectionBadge";
import { ErrorToast } from "@/components/ui/ErrorToast";
import { NoSession } from "@/components/ui/NoSession";
import { ReplayRibbon } from "@/components/ui/ReplayRibbon";
import type { JoinCredentials, Role } from "@/app/_lib/types";

export default function CallerClient() {
  const params = useSessionParams();
  const { view, status, lastError, actions } = useSession(params);
  const elapsed = useElapsed(view.state !== "ended");
  const callee = useSearchParams().get("callee") || "Grandma";
  if (!params.sessionId) return <NoSession role="caller" />;

  const aiOn = view.state === "assistant_active";
  const famOn = view.state === "family_joined";
  const ended = view.state === "ended";

  const who = ended ? "Call ended" : aiOn ? `${callee} · on hold` : famOn ? `${callee} · family on the line` : "Connected";

  // ---- Live transcription ----
  const transcription = useLiveTranscription({
    sessionId: params.sessionId,
    token: params.token,
    role: "caller",
    enabled: !ended && !params.replay,
  });

  // Wrap onJoin to also start transcription after the user's join gesture
  const handleJoin = useCallback(async (role: Role): Promise<JoinCredentials | null> => {
    const result = await actions.join(role);
    if (result) transcription.start();
    return result;
  }, [actions.join, transcription.start]);

  // ---- assistant.spoke audio ----
  const utteranceRef = useRef<string | null>(null);

  useEffect(() => {
    const spoke = view.lastAssistantUtterance;
    if (!spoke || utteranceRef.current === spoke.utterance_id) return;
    utteranceRef.current = spoke.utterance_id;

    // Stop any previous audio / speech
    window.speechSynthesis?.cancel();

    if (spoke.audio_url) {
      const base = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");
      const path = spoke.audio_url.startsWith("http") ? spoke.audio_url : `${base}${spoke.audio_url}`;
      const url = `${path}${path.includes("?") ? "&" : "?"}token=${encodeURIComponent(params.token ?? "")}`;
      const audio = new Audio(url);
      audio.play().catch(() => {
        fallbackSpeak(spoke.text);
      });
    } else {
      fallbackSpeak(spoke.text);
    }
  }, [view.lastAssistantUtterance]);

  return (
    <div className="theme-dark min-h-screen bg-paper text-ink">
      {(params.replay || view.demoReplay) && <ReplayRibbon />}

      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-line bg-card/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-lg items-center justify-between px-5 py-3">
          <ConnectionBadge status={status} />
          {!ended && (
            <span className="font-mono text-sm tabular-nums text-ink-soft">{elapsed}</span>
          )}
        </div>
      </header>

      {/* Main call area */}
      <main className="mx-auto flex min-h-[calc(100vh-52px)] max-w-lg flex-col px-5 pb-6">
        {/* Avatar + contact info */}
        <div className="flex flex-1 flex-col items-center justify-center gap-5 pt-4">
          <div className="relative">
            {!ended && (
              <span
                className={cn(
                  "absolute inset-0 rounded-full animate-pulse-ring",
                  aiOn ? "bg-cyan" : famOn ? "bg-family" : "bg-caller"
                )}
              />
            )}
            <div
              className={cn(
                "relative flex h-28 w-28 items-center justify-center rounded-full text-3xl font-semibold shadow-lg transition-all duration-500 border-2",
                aiOn
                  ? "bg-cyan-soft text-cyan border-cyan/30 shadow-cyan/20"
                  : famOn
                    ? "bg-family-soft text-family border-family/30 shadow-family/20"
                    : "bg-card text-caller border-caller/30 shadow-caller/20"
              )}
            >
              {aiOn ? (
                <svg viewBox="0 0 24 24" className="h-12 w-12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2a4 4 0 014 4v2a4 4 0 01-8 0V6a4 4 0 014-4z" />
                  <path d="M6 10a6 6 0 0012 0" />
                  <line x1="12" y1="18" x2="12" y2="22" />
                  <line x1="8" y1="22" x2="16" y2="22" />
                </svg>
              ) : famOn ? (
                <svg viewBox="0 0 24 24" className="h-12 w-12" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 00-3-3.87" />
                  <path d="M16 3.13a4 4 0 010 7.75" />
                </svg>
              ) : (
                callee.charAt(0).toUpperCase()
              )}
            </div>
          </div>

          {/* Status line */}
          <div className="text-center">
            <h1 className="text-2xl font-semibold text-ink">
              {ended ? "Call ended" : aiOn ? "Tripwire assistant" : callee}
            </h1>
            <p className={cn(
              "mt-1 text-sm font-medium",
              aiOn ? "text-cyan" : famOn ? "text-family" : "text-ink-faint"
            )}>
              {who}
            </p>
          </div>

          {/* Tripwire AI is speaking — animated cyan banner */}
          {aiOn && view.lastAssistantUtterance && (
            <div className="w-full animate-rise">
              <div className="flex items-center gap-3 rounded-2xl border border-cyan/30 bg-cyan-soft/60 px-4 py-3 shadow-[0_0_30px_-8px_rgba(59,232,217,0.25)]">
                {/* Voice wave animation */}
                <div className="flex items-center gap-[3px] h-5 shrink-0" aria-hidden="true">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <span
                      key={i}
                      className="w-[3px] rounded-full bg-cyan"
                      style={{
                        animation: `voice-wave 1.2s ease-in-out infinite`,
                        animationDelay: `${i * 0.15}s`,
                        height: "100%",
                      }}
                    />
                  ))}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-cyan">Tripwire AI is speaking</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-soft truncate">&ldquo;{view.lastAssistantUtterance.text}&rdquo;</p>
                </div>
              </div>
            </div>
          )}

          {/* AI on hold notice */}
          {aiOn && !view.lastAssistantUtterance && (
            <div className="w-full animate-rise">
              <div className="rounded-2xl border border-cyan/20 bg-cyan-soft/40 px-4 py-3">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-cyan">You are speaking with an AI assistant</p>
                <p className="mt-1 text-sm text-ink-soft">This conversation has been paused for family verification.</p>
              </div>
            </div>
          )}

          {/* Family joined notice */}
          {famOn && (
            <div className="w-full animate-rise">
              <div className="rounded-2xl border border-family/20 bg-family-soft/40 px-4 py-3">
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-family">Family member on the line</p>
                <p className="mt-1 text-sm text-ink-soft">{callee} is now being assisted by family.</p>
              </div>
            </div>
          )}

          {/* Live captions strip */}
          {!ended && <LiveCaptionsStrip transcription={transcription} />}
        </div>

        {/* Bottom controls */}
        <div className="space-y-3">
          <CallSurface
            role="caller"
            state={view.state}
            onJoin={handleJoin}
            replay={params.replay}
            compact
            sessionId={params.sessionId}
            accessToken={params.token}
          />
          {!ended && (
            <Button variant="danger" size="lg" className="w-full" onClick={() => void actions.end()}>
              Hang up
            </Button>
          )}
        </div>
      </main>
      <ErrorToast message={lastError} />
    </div>
  );
}

// ---- Live captions strip ----

function LiveCaptionsStrip({ transcription }: { transcription: ReturnType<typeof useLiveTranscription> }) {
  const { status, interim, lastFinal, error, start, stop } = transcription;
  const live = status === "live";

  return (
    <div className="w-full rounded-2xl border border-line bg-card/60 p-3.5 text-left backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <span className={cn("h-2.5 w-2.5 rounded-full shrink-0", live ? "bg-safe animate-pulse" : status === "error" ? "bg-danger" : "bg-ink-faint")} />
        <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-soft">Live captions</span>
        <span className="ml-auto text-[10px] text-ink-faint capitalize">{status}</span>
        {live ? (
          <Button size="sm" variant="ghost" onClick={stop}>Stop</Button>
        ) : (
          <Button size="sm" variant="outline" onClick={start} disabled={status === "starting"}>Start</Button>
        )}
      </div>
      {error && <p className="mt-2 text-xs text-danger">{error}</p>}
      {lastFinal && <p className="mt-2 text-sm text-ink">{lastFinal}</p>}
      {interim && <p className="mt-1 text-sm text-ink-faint italic">{interim}</p>}
      {!lastFinal && !interim && !error && <p className="mt-2 text-xs text-ink-faint">Press Start to begin live captions.</p>}
    </div>
  );
}

// ---- Helpers ----

function useElapsed(running: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, [running]);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

function fallbackSpeak(text: string) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 1;
  u.pitch = 1;
  window.speechSynthesis.speak(u);
}

