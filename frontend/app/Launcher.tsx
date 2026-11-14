"use client";
import Link from "next/link";
import { useState } from "react";
import { api, BACKEND_URL, tokenFrom } from "@/app/_lib/api";
import { roleLink } from "@/app/_lib/useSession";
import type { SessionMode } from "@/app/_lib/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Logo } from "@/components/ui/Logo";

const ROLES = [
  { id: "presenter", label: "Presenter", hint: "Big-screen dashboard: transcript, evidence, state" },
  { id: "wearer", label: "Wearer", hint: "The protected person. Large, calm warnings" },
  { id: "caller", label: "Caller", hint: "Ordinary call screen for the caller actor" },
  { id: "family", label: "Family", hint: "Trusted contact: alert, evidence, join" },
] as const;

export default function Launcher() {
  const [session, setSession] = useState<{ id: string; token: string | null } | null>(null);
  const [mode, setMode] = useState<SessionMode>("call");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const create = async () => {
    setBusy(true);
    setErr(null);
    try {
      const s = await api.createSession(mode);
      setSession({ id: s.session_id, token: tokenFrom(s) ?? null });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const replayParams = { sessionId: "replay_demo", token: null, replay: true };
  const liveParams = session ? { sessionId: session.id, token: session.token, replay: false } : null;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-center justify-between">
        <Logo />
        <span className="font-mono text-xs text-ink-faint">backend · {BACKEND_URL}</span>
      </header>

      <section className="mt-16 max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.2em] text-danger">Prototype · calls through our app</p>
        <h1 className="mt-3 font-display text-6xl font-semibold leading-[1.02] tracking-tight">A pause when it matters.</h1>
        <p className="mt-5 text-xl leading-relaxed text-ink-soft">
          Tripwire notices a high-pressure request on a call, has an identified AI assistant hold the caller,
          and brings in someone the wearer trusts — with the exact words that raised concern.
        </p>
      </section>

      <div className="mt-12 grid items-start gap-5 md:grid-cols-2">
        {/* Live */}
        <section className="rounded-3xl border border-line bg-card p-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Live session</h2>
            <div className="flex rounded-xl border border-line p-0.5 text-sm">
              {(["call", "ambient"] as const).map((m) => (
                <button key={m} onClick={() => setMode(m)} className={cn("rounded-lg px-3 py-1 font-medium capitalize", mode === m ? "bg-ink text-paper" : "text-ink-soft")}>
                  {m}
                </button>
              ))}
            </div>
          </div>
          <p className="mt-1 text-sm text-ink-soft">Creates a session on the backend with protection enabled.</p>
          {!liveParams ? (
            <Button size="lg" className="mt-5 w-full" onClick={create} loading={busy}>
              Start protected session
            </Button>
          ) : (
            <RoleLinks params={liveParams} />
          )}
          {err && <p className="mt-3 rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
          {liveParams && (
            <button className="mt-4 text-sm font-semibold text-ink-soft underline" onClick={() => setSession(null)}>
              Start a fresh session
            </button>
          )}
        </section>

        {/* Replay */}
        <section className="rounded-3xl border border-ai/30 bg-ai-soft/50 p-6">
          <h2 className="text-lg font-semibold">Demo replay</h2>
          <p className="mt-1 text-sm text-ink-soft">
            Local fixture events, synced across tabs and labeled on every page. For development and
            backup only — never presented as live inference.
          </p>
          <RoleLinks params={replayParams} />
          <p className="mt-4 text-xs text-ink-faint">Open Presenter, then press “Run replay”. Other open tabs follow along.</p>
        </section>
      </div>
    </main>
  );
}

function RoleLinks({ params }: { params: { sessionId: string; token: string | null; replay: boolean } }) {
  const [copied, setCopied] = useState<string | null>(null);
  const copy = async (role: string) => {
    try {
      await navigator.clipboard.writeText(new URL(roleLink(role, params), window.location.origin).toString());
      setCopied(role);
      setTimeout(() => setCopied(null), 1400);
    } catch {
      /* clipboard blocked */
    }
  };
  const openAll = () => ROLES.forEach((r) => window.open(roleLink(r.id, params), `tripwire-${r.id}-${params.sessionId}`));
  return (
    <div className="mt-5">
      <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-card">
        {ROLES.map((r) => (
          <li key={r.id} className="flex items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <Link href={roleLink(r.id, params)} target="_blank" className="font-semibold hover:underline">{r.label} ↗</Link>
              <p className="truncate text-xs text-ink-faint">{r.hint}</p>
            </div>
            <button onClick={() => copy(r.id)} className="rounded-lg border border-line px-2.5 py-1 text-xs font-semibold text-ink-soft hover:text-ink">
              {copied === r.id ? "Copied" : "Copy link"}
            </button>
          </li>
        ))}
      </ul>
      <Button variant="outline" className="mt-3 w-full" onClick={openAll}>Open all four windows</Button>
      {!params.replay && <p className="mt-2 font-mono text-[11px] text-ink-faint">session {params.sessionId}</p>}
    </div>
  );
}
