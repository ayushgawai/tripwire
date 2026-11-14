"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { evidenceIndex } from "@/app/_lib/reducer";
import { SCENARIOS } from "@/app/_lib/fixtures";
import { STATE_META } from "@/app/_lib/labels";
import { roleLink, useSession, useSessionParams } from "@/app/_lib/useSession";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { cn } from "@/components/ui/cn";
import { ConnectionBadge } from "@/components/ui/ConnectionBadge";
import { ErrorToast } from "@/components/ui/ErrorToast";
import { EventLog } from "@/components/ui/EventLog";
import { EvidenceList } from "@/components/ui/EvidenceList";
import { Logo } from "@/components/ui/Logo";
import { NoSession } from "@/components/ui/NoSession";
import { Pulse } from "@/components/ui/Pulse";
import { ReplayRibbon } from "@/components/ui/ReplayRibbon";
import { RiskPanel } from "@/components/ui/RiskPanel";
import { RoutingDiagram } from "@/components/ui/RoutingDiagram";
import { StatePill } from "@/components/ui/StatePill";
import { StateTimeline } from "@/components/ui/StateTimeline";
import { Transcript } from "@/components/ui/Transcript";

export default function PresenterClient() {
  const params = useSessionParams();
  const { view, status, lastError, actions } = useSession(params);
  const [scenario, setScenario] = useState(params.scenario ?? "scam");
  const [showLog, setShowLog] = useState(true);
  const autoplay = useSearchParams().get("autoplay");
  const { runScenario } = actions;
  useEffect(() => {
    if (!params.replay || !autoplay) return;
    const t = setTimeout(() => runScenario(params.scenario ?? "scam"), 600);
    return () => clearTimeout(t);
  }, [params.replay, params.scenario, autoplay, runScenario]);
  if (!params.sessionId) return <NoSession role="presenter" />;

  const ev = evidenceIndex(view);
  const evidence = view.latestDecision?.evidence.length
    ? view.latestDecision.evidence
    : view.alert?.evidence ?? [];
  const meta = STATE_META[view.state];
  const high = view.latestDecision?.risk === "high";

  return (
    <div className="theme-dark min-h-screen text-ink">
      {(params.replay || view.demoReplay) && <ReplayRibbon />}
      {/* ---------- Top bar ---------- */}
      <header className="sticky top-0 z-40 border-b border-line bg-card/80 backdrop-blur">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-3 px-5 py-2.5">
          <Logo />
          <span className="hidden font-mono text-[11px] tabular-nums text-ink-faint md:inline">
            {view.session_id || params.sessionId}
          </span>
          <StatePill state={view.state} takeover={view.takeover} />
          <ConnectionBadge status={status} />
          <nav className="ml-auto flex flex-wrap items-center gap-1.5 text-sm">
            {(["wearer", "caller", "family"] as const).map((r) => (
              <Link
                key={r}
                href={roleLink(r, params)}
                target="_blank"
                className="rounded-lg px-2.5 py-1.5 text-ink-soft hover:bg-line/60 hover:text-ink"
              >
                {r[0].toUpperCase() + r.slice(1)}
                <span className="ml-0.5 text-ink-faint">↗</span>
              </Link>
            ))}
          </nav>
          {params.replay ? (
            <div className="flex items-center gap-2">
              <select
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                className="h-9 rounded-xl border border-line bg-paper px-3 text-xs text-ink"
              >
                {SCENARIOS.map((s) => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
              <Button size="sm" onClick={() => void actions.runScenario(scenario)}>Run replay</Button>
              <Button variant="outline" size="sm" onClick={actions.resetReplay}>Reset</Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Link href="/" className="inline-flex h-9 items-center rounded-xl border border-line bg-card px-3.5 text-xs font-semibold">
                New session
              </Link>
              {view.state !== "ended" && <Button variant="danger" size="sm" onClick={() => void actions.end()}>End session</Button>}
            </div>
          )}
        </div>
      </header>

      <main className="mx-auto grid max-w-[1500px] gap-4 px-5 py-4">
        {/* ---------- Hero row: state info + routing diagram ---------- */}
        <section
          className={cn(
            "relative overflow-hidden rounded-2xl border p-5 transition-colors duration-700",
            view.takeover === "failed" ? "border-danger/50 bg-danger-soft"
              : view.state === "assistant_active" ? "border-danger/30 bg-danger-soft"
              : view.state === "protecting" ? "border-watch/30 bg-watch-soft"
              : view.state === "family_joined" ? "border-violet/30 bg-violet-soft"
              : "border-line bg-card",
          )}
        >
          <div className="grid items-center gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)]">
            {/* Left: state headline + timeline */}
            <div className="flex flex-col justify-center">
              <p className="text-[11px] font-medium text-ink-faint">Session state</p>
              <h1 key={view.state + view.takeover} className="mt-1 font-display text-4xl font-semibold tracking-tight lg:text-5xl">
                {view.takeover === "failed" && view.state !== "family_joined" ? "Takeover failed" : meta.label}
              </h1>
              <p className="mt-2 max-w-md text-[13px] text-ink-soft leading-relaxed">
                {view.takeover === "failed" ? view.takeoverError : meta.blurb}
              </p>
              <div className="mt-5">
                <StateTimeline state={view.state} timeline={view.timeline} failed={view.takeover === "failed"} />
              </div>
            </div>
            {/* Right: hero routing diagram */}
            <div className="flex flex-col justify-center">
              <div className="mx-auto w-full max-w-[560px] rounded-xl border border-line/60 bg-paper/60 p-4">
                <RoutingDiagram view={view} />
              </div>
            </div>
          </div>
        </section>

        {/* ---------- Content grid ---------- */}
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          {/* ---------- Transcript ---------- */}
          <Card
            title="Live transcript"
            aside={
              <span className="inline-flex items-center gap-2 text-[11px] text-ink-faint">
                <Pulse tone={status === "live" ? "safe" : status === "replay" ? "ai" : "muted"} size={6} still={status !== "live" && status !== "replay"} />
                <span className="tabular-nums">{view.transcript.length} finalized</span>
                <span className="text-ink-faint/60">· {view.mode}</span>
              </span>
            }
            className="flex min-h-[440px] flex-col lg:row-span-2"
          >
            <Transcript utterances={view.transcript} evidence={ev} large className="max-h-[58vh] flex-1" />
          </Card>

          {/* ---------- Risk ---------- */}
          <Card
            title="Risk decision"
            aside={high ? <span className="rounded-full bg-danger px-2 py-0.5 text-[10px] font-bold text-white uppercase tracking-wider">High</span> : null}
          >
            <RiskPanel decision={view.latestDecision} history={view.decisions} />
          </Card>

          <Card title="Family">
            <FamilyStatus view={view} />
          </Card>
        </div>

        {/* ---------- Evidence ---------- */}
        <Card
          title="Supporting quotes"
          aside={<span className="text-[11px] text-ink-faint">Each quote is checked against its utterance</span>}
        >
          {evidence.length ? (
            <EvidenceList evidence={evidence} transcript={view.transcript} className="grid gap-4 space-y-0 md:grid-cols-2 xl:grid-cols-3" />
          ) : (
            <p className="text-sm text-ink-faint">No evidence yet.</p>
          )}
        </Card>

        {/* ---------- Errors + log ---------- */}
        <Card
          title="Event stream"
          aside={
            <button className="text-[11px] font-semibold text-ink-soft" onClick={() => setShowLog((s) => !s)}>
              {showLog ? "Hide" : "Show"} · last seq #<span className="tabular-nums">{view.lastSequence}</span>
            </button>
          }
        >
          {view.errors.length > 0 && (
            <ul className="mb-3 space-y-1">
              {view.errors.map((e, i) => (
                <li key={i} className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{e.message}</li>
              ))}
            </ul>
          )}
          {showLog && <EventLog events={view.log} className="max-h-56" />}
        </Card>
      </main>
      <ErrorToast message={lastError} />
    </div>
  );
}

function FamilyStatus({ view }: { view: ReturnType<typeof useSession>["view"] }) {
  const steps = [
    { label: "Alert sent", done: !!view.alert },
    { label: "Family joined (call event)", done: view.familyJoined },
    { label: "Assistant stopped", done: view.familyJoined },
    { label: "Wearer reconnected", done: view.wearerReconnected },
  ];
  return (
    <ol className="space-y-2.5">
      {steps.map((s) => (
        <li key={s.label} className="flex items-center gap-3 text-sm">
          <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-full border", s.done ? "border-violet bg-violet text-paper" : "border-line text-transparent")}>
            <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M3.5 8.5l3 3 6-7" /></svg>
          </span>
          <span className={s.done ? "text-ink" : "text-ink-faint"}>{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
