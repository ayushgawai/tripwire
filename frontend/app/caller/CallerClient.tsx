"use client";
// The caller sees an ordinary calling screen. No risk scores, no evidence — only what they would
// legitimately hear: the Tripwire assistant identifies itself, and later a family member joins.
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useSession, useSessionParams } from "@/app/_lib/useSession";
import { Button } from "@/components/ui/Button";
import { CallSurface } from "@/components/ui/CallSurface";
import { cn } from "@/components/ui/cn";
import { ConnectionBadge } from "@/components/ui/ConnectionBadge";
import { ErrorToast } from "@/components/ui/ErrorToast";
import { NoSession } from "@/components/ui/NoSession";
import { ReplayRibbon } from "@/components/ui/ReplayRibbon";

export default function CallerClient() {
  const params = useSessionParams();
  const { view, status, lastError, actions } = useSession(params);
  const elapsed = useElapsed(view.state !== "ended");
  const callee = useSearchParams().get("callee") || "Grandma";
  if (!params.sessionId) return <NoSession role="caller" />;

  const assistantLines = view.transcript.filter((u) => u.speaker === "assistant" || u.speaker === "family");
  const latest = assistantLines[assistantLines.length - 1];
  const aiOn = view.state === "assistant_active";
  const famOn = view.state === "family_joined";
  const ended = view.state === "ended";

  const who = ended ? "Call ended" : aiOn ? `${callee} · on hold` : famOn ? `${callee} · family on the line` : "Connected";
  return (
    <div className="theme-dark min-h-screen bg-paper text-ink">
      {params.replay && <ReplayRibbon />}
      <main className="mx-auto flex min-h-screen max-w-md flex-col px-6 py-6">
        <div className="flex justify-end"><ConnectionBadge status={status} /></div>

        <div className="flex flex-1 flex-col items-center justify-center gap-6 text-center">
          <div className="relative">
            {!ended && <span className={cn("absolute inset-0 rounded-full animate-pulse-ring", aiOn ? "bg-ai" : famOn ? "bg-family" : "bg-safe")} />}
            <div className={cn("relative flex h-32 w-32 items-center justify-center rounded-full text-4xl font-semibold transition-colors",
              aiOn ? "bg-ai-soft text-ai" : famOn ? "bg-family-soft text-family" : "bg-card text-ink-soft")}>
              {aiOn ? "AI" : famOn ? "F" : callee.charAt(0).toUpperCase()}
            </div>
          </div>
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-ink-faint">{who}</p>
            <h1 className="mt-1 text-3xl font-semibold">{aiOn ? "Tripwire assistant" : callee}</h1>
            <p className="mt-1 font-mono text-ink-faint">{ended ? "—" : elapsed}</p>
          </div>

          {aiOn && (
            <div className="w-full rounded-2xl border border-ai/30 bg-ai-soft p-4 text-left animate-rise">
              <p className="text-xs font-bold uppercase tracking-wider text-ai">You are speaking with an AI assistant</p>
              <p className="mt-1 text-sm text-ink-soft">This conversation has been paused for family verification.</p>
            </div>
          )}

          {latest && !ended && (
            <p key={latest.utterance_id} className="max-w-sm animate-rise text-lg leading-relaxed text-ink">
              “{latest.text}”
            </p>
          )}
        </div>

        <div className="space-y-4">
          <CallSurface role="caller" state={view.state} onJoin={actions.join} replay={params.replay} compact />
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

function useElapsed(running: boolean) {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setS((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, [running]);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}
