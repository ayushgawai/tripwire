"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, BACKEND_URL, type CreatedSession } from "@/app/_lib/api";
import { roleLink } from "@/app/_lib/useSession";
import type { SessionMode } from "@/app/_lib/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/components/ui/cn";
import { Logo } from "@/components/ui/Logo";

const ROLES = [
  {
    id: "presenter",
    label: "Presenter",
    hint: "Big-screen dashboard: transcript, evidence, state",
    color: "cyan",
    glyph: "P",
  },
  {
    id: "wearer",
    label: "Wearer",
    hint: "The protected person. Large, calm warnings",
    color: "watch",
    glyph: "W",
  },
  {
    id: "caller",
    label: "Caller",
    hint: "Ordinary call screen for the caller actor",
    color: "caller",
    glyph: "C",
  },
  {
    id: "family",
    label: "Family",
    hint: "Trusted contact: alert, evidence, join",
    color: "family",
    glyph: "F",
  },
] as const;

const COLOR_MAP: Record<string, { ring: string; bg: string; text: string; border: string; glow: string }> = {
  cyan: {
    ring: "ring-cyan",
    bg: "bg-cyan-soft",
    text: "text-cyan",
    border: "border-cyan/30",
    glow: "bg-cyan/20",
  },
  watch: {
    ring: "ring-watch",
    bg: "bg-watch-soft",
    text: "text-watch",
    border: "border-watch/30",
    glow: "bg-watch/20",
  },
  caller: {
    ring: "ring-caller",
    bg: "bg-caller-soft",
    text: "text-caller",
    border: "border-caller/30",
    glow: "bg-caller/20",
  },
  family: {
    ring: "ring-family",
    bg: "bg-family-soft",
    text: "text-family",
    border: "border-family/30",
    glow: "bg-family/20",
  },
};

export default function Launcher() {
  const [session, setSession] = useState<{ id: string; tokens: CreatedSession["tokens"] } | null>(null);
  const [health, setHealth] = useState<"checking" | "up" | "down">("checking");
  useEffect(() => {
    let alive = true;
    api.health().then(() => alive && setHealth("up"), () => alive && setHealth("down"));
    return () => { alive = false; };
  }, []);
  const [mode, setMode] = useState<SessionMode>("call");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const create = async () => {
    setBusy(true);
    setErr(null);
    try {
      const s = await api.createSession(mode);
      if (!s.tokens) throw new Error("Backend did not return role tokens");
      setSession({ id: s.session_id, tokens: s.tokens });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const replayParams: LinkParams = { sessionId: "replay_demo", token: null, replay: true };
  const liveParams = session ? { sessionId: session.id, token: null, tokens: session.tokens, replay: false } : null;

  return (
    <div className="theme-dark min-h-screen text-ink">
      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Top bar */}
        <header className="flex items-center justify-between">
          <Logo />
          <span className="inline-flex items-center gap-2 font-mono text-xs text-ink-faint">
            <span className={cn("h-2 w-2 rounded-full", health === "up" ? "bg-safe" : health === "down" ? "bg-danger" : "bg-watch")} />
            backend {health === "up" ? "up" : health === "down" ? "unreachable" : "…"} · {BACKEND_URL}
          </span>
        </header>

        {/* Hero split */}
        <div className="mt-16 grid items-start gap-10 lg:grid-cols-[1fr_1.1fr]">
          {/* Left: headline + controls */}
          <section className="flex flex-col">
            <h1 className="font-display text-5xl font-semibold leading-[1.08] tracking-tight text-ink sm:text-6xl">
              Pause a risky call and bring in family.
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-ink-soft">
              Tripwire notices a high-pressure request on a call, has an AI assistant hold the caller,
              and brings in someone the wearer trusts — with the exact words that raised concern.
            </p>

            {/* Mode toggle + Start */}
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <div className="inline-flex rounded-2xl border border-line bg-paper p-1 text-sm">
                {(["call", "ambient"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={cn(
                      "rounded-xl px-4 py-2 font-medium capitalize transition-all",
                      mode === m ? "bg-ink text-paper shadow-sm" : "text-ink-soft hover:text-ink"
                    )}
                    aria-pressed={mode === m}
                  >
                    {m}
                  </button>
                ))}
              </div>
              {!liveParams && (
                <Button size="xl" onClick={create} loading={busy} className="shadow-lg shadow-ink/10">
                  Start session
                </Button>
              )}
            </div>
            {err && (
              <div className="mt-4 rounded-2xl bg-danger-soft px-4 py-3 text-sm text-danger border border-danger/20">{err}</div>
            )}
            {liveParams && (
              <button
                className="mt-4 text-sm font-semibold text-ink-faint hover:text-ink transition-colors"
                onClick={() => setSession(null)}
              >
                Start a fresh session
              </button>
            )}
          </section>

          {/* Right: role cards + demo */}
          <section className="flex flex-col gap-5">
            {liveParams ? (
              /* Live role cards */
              <div className="rounded-3xl border border-line bg-card p-5 shadow-xl shadow-ink/5">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint">Session windows</p>
                  <span className="font-mono text-[11px] tabular-nums text-ink-faint/60">{liveParams.sessionId}</span>
                </div>
                <div className="grid grid-cols-2 gap-2.5">
                  {ROLES.map((r) => {
                    const c = COLOR_MAP[r.color];
                    return (
                      <div
                        key={r.id}
                        className="group relative overflow-hidden rounded-2xl border border-line bg-paper p-3.5 transition-all hover:border-ink-faint/50"
                      >
                        {/* Colored accent bar */}
                        <div className={cn("absolute left-0 top-3 bottom-3 w-[3px] rounded-full", c.glow)} />
                        <div className="pl-2">
                          <div className="flex items-center gap-2.5">
                            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold", c.bg, c.text)}>
                              {r.glyph}
                            </span>
                            <div>
                              <Link
                                href={roleLink(r.id, liveParams)}
                                target="_blank"
                                className="text-sm font-semibold text-ink hover:text-caller transition-colors"
                              >
                                {r.label} <span className="text-ink-faint group-hover:text-caller transition-colors">&#8599;</span>
                              </Link>
                            </div>
                          </div>
                          <p className="mt-1.5 pl-[42px] text-[11px] leading-snug text-ink-faint">{r.hint}</p>
                          <div className="mt-2.5 pl-[42px] flex items-center gap-2">
                            <Link
                              href={roleLink(r.id, liveParams)}
                              target="_blank"
                              className="inline-flex items-center rounded-lg border border-line px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-ink hover:border-ink-faint transition-colors"
                            >
                              Open
                            </Link>
                            <CopyLinkButton roleId={r.id} params={liveParams} />
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <Button
                  variant="outline"
                  size="md"
                  className="mt-3.5 w-full"
                  onClick={() => ROLES.forEach((r) => window.open(roleLink(r.id, liveParams), `tripwire-${r.id}-${liveParams.sessionId}`))}
                >
                  Open all four windows
                </Button>
              </div>
            ) : (
              /* Preview cards (no session yet) */
              <div className="rounded-3xl border border-line/60 bg-card/40 p-5">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint/60 mb-4">Role windows</p>
                <div className="grid grid-cols-2 gap-2.5">
                  {ROLES.map((r) => {
                    const c = COLOR_MAP[r.color];
                    return (
                      <div
                        key={r.id}
                        className="rounded-2xl border border-line/60 bg-paper/60 p-3.5"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold opacity-60", c.bg, c.text)}>
                            {r.glyph}
                          </span>
                          <span className="text-sm font-semibold text-ink-faint/70">{r.label}</span>
                        </div>
                        <p className="mt-1.5 pl-[42px] text-[11px] leading-snug text-ink-faint/50">{r.hint}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Demo replay — clearly labeled, secondary */}
            <section className="rounded-2xl border border-ai/15 bg-ai-soft/20 p-5">
              <h2 className="text-sm font-semibold text-ai/80">Demo replay</h2>
              <p className="mt-1 text-xs text-ink-faint/70 leading-relaxed">
                Local fixture events, synced across tabs. For development and demo only — not live inference.
              </p>
              <RoleGrid params={replayParams} />
              <p className="mt-3 text-[11px] text-ink-faint/50">
                Open Presenter, then press "Run replay". Other open tabs follow along.
              </p>
            </section>
          </section>
        </div>
      </div>
    </div>
  );
}

type LinkParams = Parameters<typeof roleLink>[1];

function CopyLinkButton({ roleId, params }: { roleId: string; params: LinkParams }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(new URL(roleLink(roleId, params), window.location.origin).toString());
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* clipboard blocked */
    }
  };
  return (
    <button
      onClick={copy}
      className="inline-flex items-center rounded-lg border border-line px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-ink hover:border-ink-faint transition-colors"
    >
      {copied ? "Copied" : "Copy link"}
    </button>
  );
}

function RoleGrid({ params }: { params: LinkParams }) {
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
    <div className="mt-4">
      <div className="grid grid-cols-2 gap-2">
        {ROLES.map((r) => (
          <div
            key={r.id}
            className="flex flex-col gap-1.5 rounded-xl border border-line/60 bg-paper/60 px-3 py-2.5"
          >
            <Link
              href={roleLink(r.id, params)}
              target="_blank"
              className="text-sm font-semibold text-ink-soft hover:text-ink hover:underline transition-colors"
            >
              {r.label} <span aria-hidden="true" className="text-ink-faint">&#8599;</span>
            </Link>
            <p className="text-[11px] leading-snug text-ink-faint/60">{r.hint}</p>
            <button
              onClick={() => copy(r.id)}
              className="mt-1 self-start rounded-lg border border-line/60 px-2 py-0.5 text-[11px] font-semibold text-ink-soft hover:text-ink transition-colors"
            >
              {copied === r.id ? "Copied" : "Copy link"}
            </button>
          </div>
        ))}
      </div>
      <Button variant="outline" className="mt-3 w-full" size="md" onClick={openAll}>Open all four windows</Button>
      {!params.replay && <p className="mt-2 font-mono text-[11px] text-ink-faint/50">session {params.sessionId}</p>}
    </div>
  );
}
