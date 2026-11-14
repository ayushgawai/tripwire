"use client";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import type { JoinCredentials } from "@/app/_lib/types";
import { chime, flashTitle, notify, requestNotify, unlockAudio } from "@/app/_lib/alerts";
import { timeOf } from "@/app/_lib/labels";
import { evidenceIndex } from "@/app/_lib/reducer";
import { useSession, useSessionParams } from "@/app/_lib/useSession";
import { Button } from "@/components/ui/Button";
import { CallSurface } from "@/components/ui/CallSurface";
import { Card } from "@/components/ui/Card";
import { cn } from "@/components/ui/cn";
import { ConnectionBadge } from "@/components/ui/ConnectionBadge";
import { ErrorToast } from "@/components/ui/ErrorToast";
import { EvidenceList } from "@/components/ui/EvidenceList";
import { Logo } from "@/components/ui/Logo";
import { NoSession } from "@/components/ui/NoSession";
import { Pulse } from "@/components/ui/Pulse";
import { ReplayRibbon } from "@/components/ui/ReplayRibbon";
import { ReasonChips } from "@/components/ui/RiskPanel";
import { StatePill } from "@/components/ui/StatePill";
import { Transcript } from "@/components/ui/Transcript";

const JOIN_TIMEOUT_MS = 15000;

export default function FamilyClient() {
  const params = useSessionParams();
  const wearer = useSearchParams().get("wearer") || "Mom";
  const { view, status, lastError, actions } = useSession(params);
  const [soundOn, setSoundOn] = useState(false);
  const [joining, setJoining] = useState(false);
  const [joinSlow, setJoinSlow] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [creds, setCreds] = useState<JoinCredentials | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const alerted = useRef<string | null>(null);

  // Ring once per distinct alert (refreshing the page recovers state but doesn't re-ring).
  useEffect(() => {
    if (!view.alert) return;
    const key = view.alert.decision_id ?? view.alert.summary;
    if (alerted.current === key) return;
    const firstLoad = alerted.current === null && status !== "replay" && view.log.length === 0;
    alerted.current = key;
    if (firstLoad) return;
    chime();
    notify(`${wearer} may be in a risky call`, view.alert.summary);
    return flashTitle(`${wearer} needs you`);
  }, [view.alert, wearer, status, view.log.length]);

  // Joined state comes only from the real family.joined event.
  useEffect(() => {
    if (view.familyJoined) {
      setJoining(false);
      setJoinSlow(false);
    }
  }, [view.familyJoined]);
  useEffect(() => {
    if (!joining) return;
    const t = setTimeout(() => setJoinSlow(true), JOIN_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [joining]);
  useEffect(() => {
    if (view.wearerReconnected) setReconnecting(false);
  }, [view.wearerReconnected]);

  if (!params.sessionId) return <NoSession role="family" />;

  const enableSound = async () => {
    setSoundOn(unlockAudio());
    await requestNotify();
  };

  const join = async () => {
    unlockAudio();
    setJoining(true);
    setJoinSlow(false);
    const c = await actions.join("family");
    if (!c) setJoining(false);
    else setCreds(c);
  };

  const ev = evidenceIndex(view);
  const alert = view.alert;
  const ended = view.state === "ended";

  return (
    <div className={cn("min-h-screen transition-colors duration-700", alert && !view.familyJoined && !ended ? "bg-danger-soft/60" : "bg-paper")}>
      {params.replay && <ReplayRibbon />}
      <header className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-5 py-5">
        <div className="flex items-center gap-3">
          <Logo />
          <span className="hidden text-sm text-ink-faint sm:inline">Trusted contact for {wearer}</span>
        </div>
        <div className="flex items-center gap-2">
          <StatePill state={view.state} takeover={view.takeover} className="hidden sm:inline-flex" />
          <ConnectionBadge status={status} />
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-5 px-5 pb-20">
        {!alert ? (
          <StandBy wearer={wearer} soundOn={soundOn} onEnableSound={enableSound} ended={ended} />
        ) : (
          <>
            {/* ---------- Alert hero ---------- */}
            <section
              className={cn(
                "relative overflow-hidden rounded-[2rem] border p-6 sm:p-8 animate-rise",
                view.familyJoined ? "border-family/30 bg-card" : "border-danger/30 bg-card shadow-[0_20px_60px_-20px_rgba(210,63,49,0.35)]",
              )}
            >
              <div className="flex items-start gap-4">
                <span className={cn("mt-1 flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl", view.familyJoined ? "bg-family-soft text-family" : "bg-danger text-white")}>
                  <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    {view.familyJoined ? <path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z" /> : (<><path d="M12 3l9.5 17h-19L12 3z" /><path d="M12 10v4M12 17.5v.01" /></>)}
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn("text-xs font-bold uppercase tracking-[0.18em]", view.familyJoined ? "text-family" : "text-danger")}>
                    {view.familyJoined ? "You're on the call" : "Tripwire alert"} {alert.timestamp && `· ${timeOf(alert.timestamp)}`}
                  </p>
                  <h1 className="mt-1 font-display text-3xl font-semibold leading-tight sm:text-4xl">
                    {view.familyJoined ? `You're helping ${wearer} now` : `${wearer} may be in a risky call`}
                  </h1>
                  <p className="mt-3 text-lg leading-relaxed text-ink-soft">{alert.summary}</p>
                  <ReasonChips reasons={alert.reasons} className="mt-4" />
                </div>
              </div>

              <ProtectionStatus view={view} wearer={wearer} />

              {/* ---------- Primary action ---------- */}
              {!ended && (
                <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
                  {!view.familyJoined ? (
                    <>
                      <Button variant="family" size="xl" onClick={join} loading={joining} className="w-full sm:w-auto">
                        {joining ? "Joining call…" : "Join the call"}
                      </Button>
                      <p className="text-sm text-ink-faint">
                        {joining
                          ? joinSlow
                            ? "Still waiting for the call to confirm you joined. Check your connection or try again."
                            : "Waiting for the call to confirm you're connected."
                          : "The assistant stops speaking as soon as you join."}
                      </p>
                    </>
                  ) : !view.wearerReconnected ? (
                    <>
                      <Button
                        variant="primary"
                        size="lg"
                        loading={reconnecting}
                        onClick={async () => { setReconnecting(true); await actions.reconnectWearer(); }}
                      >
                        Reconnect {wearer}
                      </Button>
                      <p className="text-sm text-ink-faint">{wearer} stays protected until you choose to bring them back.</p>
                    </>
                  ) : (
                    <p className="inline-flex items-center gap-2 font-semibold text-family"><Pulse tone="family" size={8} /> {wearer} is back on the call with you.</p>
                  )}
                  <Button variant="ghost" className="sm:ml-auto" onClick={() => void actions.end()}>
                    End call for everyone
                  </Button>
                </div>
              )}
              {ended && <p className="mt-6 font-semibold text-ink-soft">The call has ended.</p>}
            </section>

            {/* ---------- Evidence ---------- */}
            <Card title="What was said" aside={<span className="text-xs text-ink-faint">Exact quotes from the call</span>}>
              <EvidenceList evidence={alert.evidence} transcript={view.transcript} large />
            </Card>

            <Card
              title="Full transcript"
              aside={
                <button className="text-sm font-semibold text-family" onClick={() => setShowTranscript((s) => !s)}>
                  {showTranscript ? "Hide" : `Show (${view.transcript.length})`}
                </button>
              }
            >
              {showTranscript ? (
                <Transcript utterances={view.transcript} evidence={ev} className="max-h-[420px]" />
              ) : (
                <p className="text-sm text-ink-faint">Context for the quotes above, including what the Tripwire assistant said.</p>
              )}
            </Card>

            {(creds || view.familyJoined) && (
              <CallSurface role="family" state={view.state} onJoin={actions.join} replay={params.replay} credentials={creds} compact />
            )}
          </>
        )}
      </main>
      <ErrorToast message={lastError} />
    </div>
  );
}

function ProtectionStatus({ view, wearer }: { view: ReturnType<typeof useSession>["view"]; wearer: string }) {
  const rows: { label: string; tone: "safe" | "watch" | "danger" | "family" | "muted"; on: boolean }[] = [];
  if (view.takeover === "failed") rows.push({ label: "Automatic pause failed — call may still be live", tone: "danger", on: true });
  else if (view.takeover === "starting") rows.push({ label: `Pausing the caller for ${wearer}…`, tone: "watch", on: true });
  else if (view.takeover === "active") rows.push({ label: `${wearer} can't hear the caller`, tone: "safe", on: true });
  if (view.state === "assistant_active") rows.push({ label: "Tripwire AI is holding the caller", tone: "watch", on: true });
  if (view.familyJoined) rows.push({ label: "You joined · assistant stopped", tone: "family", on: true });
  if (!rows.length) return null;
  return (
    <ul className="mt-5 flex flex-wrap gap-2">
      {rows.map((r) => (
        <li key={r.label} className="inline-flex items-center gap-2 rounded-full border border-line bg-paper px-3 py-1.5 text-sm font-medium">
          <Pulse tone={r.tone} size={8} /> {r.label}
        </li>
      ))}
    </ul>
  );
}

function StandBy({ wearer, soundOn, onEnableSound, ended }: { wearer: string; soundOn: boolean; onEnableSound: () => void; ended: boolean }) {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center gap-6 text-center animate-rise">
      <span className="relative flex h-24 w-24 items-center justify-center rounded-full bg-safe-soft text-safe">
        {!ended && <span className="absolute inset-0 rounded-full bg-safe/20 animate-pulse-ring" />}
        <svg viewBox="0 0 24 24" className="h-11 w-11" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l7 3v5c0 4.5-3 8.4-7 10-4-1.6-7-5.5-7-10V6l7-3z" /><path d="M9 12l2 2 4-4" />
        </svg>
      </span>
      <div className="space-y-2">
        <h1 className="font-display text-4xl font-semibold">{ended ? "Session ended" : "All quiet"}</h1>
        <p className="mx-auto max-w-md text-lg text-ink-soft">
          {ended
            ? "No alerts were raised in this session."
            : `You're ${wearer}'s trusted contact. If a call looks risky, this page will alert you with exactly what was said.`}
        </p>
      </div>
      {!ended && (
        <Button variant={soundOn ? "outline" : "primary"} size="lg" onClick={onEnableSound} disabled={soundOn}>
          {soundOn ? "Sound alerts on" : "Turn on sound alerts"}
        </Button>
      )}
    </section>
  );
}
