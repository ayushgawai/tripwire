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
    <div className="launch-page theme-dark min-h-screen text-ink">
      <div className="mx-auto max-w-6xl px-4 py-7 sm:px-6">
        {/* Top bar */}
        <header className="flex items-center justify-between">
          <Logo />
          <span className="backend-health inline-flex items-center gap-2 font-mono text-xs text-ink-faint">
            <span className={cn("h-2 w-2 rounded-full", health === "up" ? "bg-safe" : health === "down" ? "bg-danger" : "bg-watch")} />
            backend {health === "up" ? "up" : health === "down" ? "unreachable" : "…"} · {BACKEND_URL}
          </span>
        </header>

        <section className="launch-hero">
          <div className="aurora" aria-hidden="true" />
          <div className="launch-copy">
            <p className="eyebrow">Introducing Tripwire</p>
            <h1>A <span className="champagne-text">pause</span> when<br className="hidden sm:block" /> it matters.</h1>
            <p className="hero-description">Quiet protection, worn every day. Tripwire runs on the Vexo band that listens with you all day, and also protects calls made through our app.</p>
            <p className="hero-detail">When a request feels wrong, a moment to pause.<br />And someone you trust, right there with you.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#live-demo" className="tw-button inline-flex items-center justify-center rounded-[14px] border border-champagne/40 px-6 py-3.5 text-sm font-semibold">Watch it work</a>
              <Button size="lg" onClick={create} loading={busy}>Start a protected session</Button>
            </div>
            {err && <p role="alert" className="mt-4 text-sm text-danger">{err}</p>}
            {liveParams && <a href="#live-demo" className="mt-4 inline-block text-sm text-champagne underline underline-offset-4">Session ready. Open your role windows below.</a>}
            <p className="mt-5 text-xs text-ink-faint">Designed for the Vexo band. Built around the people you trust.</p>
          </div>
          <figure className="product-illustration" aria-label="Illustration of a Vexo wristband beside a protected phone call">
            <div className="product-orbit" aria-hidden="true" />
            <div className="band-illustration" aria-hidden="true">
              <div className="band-strap" />
              <div className="band-face"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 18h7l4-8 5 14 4-8h6" /></svg><span>VEXO</span></div>
              <div className="band-clasp" />
            </div>
            <div className="phone-illustration">
              <div className="phone-speaker" />
              <div className="flex items-center justify-between"><Logo compact /><span className="text-xs text-ink-soft">Protected call</span></div>
              <div className="phone-contact"><span>M</span><p>Mom</p><small>Call through Tripwire</small></div>
              <div className="illustration-status"><span className="illustration-monitor">Monitoring</span><span className="illustration-active">Assistant active</span></div>
              <div className="illustration-quote"><p className="text-xs text-ink-soft">Caller</p><blockquote>“Please <mark className="evidence">buy the gift cards</mark> and <mark className="evidence">keep this between us.</mark>”</blockquote></div>
              <div className="illustration-family"><span className="h-2 w-2 rounded-full bg-family" /><div><p>Family alerted</p><small>The exact words. A chance to help.</small></div></div>
              <div className="phone-home" />
            </div>
            <figcaption><span>Vexo band + Tripwire</span><span>Illustration</span></figcaption>
          </figure>
        </section>

        <section className="how-it-works" aria-labelledby="how-title">
          <div className="section-heading"><p className="eyebrow">How it works</p><h2 id="how-title">A little space. A better decision.</h2></div>
          <div className="how-grid">
            <article><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="9" y="7" width="14" height="18" rx="6" /><path d="M12 7V2h8v5M12 25v5h8v-5M12 16h3l2-4 2 7 2-3" /></svg><span className="step-number">01</span><h3>Detects pressure</h3><p>The Vexo band listens with you all day. Tripwire also watches for high-pressure requests in calls through our app.</p></article>
            <article><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="16" cy="16" r="12" /><path d="M12 11v10M20 11v10" /></svg><span className="step-number">02</span><h3>Pauses the call</h3><p>An identified AI assistant holds the caller while you receive a calm warning and a moment to think.</p></article>
            <article><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><circle cx="12" cy="10" r="4" /><path d="M3 27v-4a9 9 0 0118 0v4M22 7a4 4 0 010 8M24 19a7 7 0 015 6" /></svg><span className="step-number">03</span><h3>Brings in family</h3><p>Someone you trust gets the exact words that raised concern and can join the call to help.</p></article>
          </div>
        </section>
        <div className="principles-strip"><span>Identifies itself as AI</span><span>Never speaks for you</span><span>Never moves money</span><span>Family decides when you rejoin</span></div>

        <div id="live-demo" className="demo-console mt-20 grid items-start gap-8 lg:grid-cols-[1fr_1.1fr]">
          <section className="flex flex-col">
            <p className="eyebrow">Experience Tripwire</p>
            <h2 className="mt-3 font-display text-4xl font-normal sm:text-5xl">Try the live demo.</h2>
            <p className="mt-4 max-w-md text-base leading-relaxed text-ink-soft">Start a session, then open each perspective. Follow the call from the wearer to the person they trust.</p>

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
                  <span className="font-mono text-[11px] tabular-nums text-ink-faint">{liveParams.sessionId}</span>
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
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-ink-faint mb-4">Role windows</p>
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
                          <span className="text-sm font-semibold text-ink-faint">{r.label}</span>
                        </div>
                        <p className="mt-1.5 pl-[42px] text-[11px] leading-snug text-ink-faint">{r.hint}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Demo replay — clearly labeled, secondary */}
            <section className="rounded-2xl border border-ai/15 bg-ai-soft/20 p-5">
              <h2 className="text-sm font-semibold text-ai/80">Demo replay</h2>
              <p className="mt-1 text-xs text-ink-faint leading-relaxed">
                Local fixture events, synced across tabs. For development and demo only — not live inference.
              </p>
              <RoleGrid params={replayParams} />
              <p className="mt-3 text-[11px] text-ink-faint">
                Open Presenter, then press "Run replay". Other open tabs follow along.
              </p>
            </section>
          </section>
        </div>
        <footer className="launch-footer"><Logo /><p>Prototype. Calls through our app.</p><span>Built for Vexo Hacks</span></footer>
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
            <p className="text-[11px] leading-snug text-ink-faint">{r.hint}</p>
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
      {!params.replay && <p className="mt-2 font-mono text-[11px] text-ink-faint">session {params.sessionId}</p>}
    </div>
  );
}
