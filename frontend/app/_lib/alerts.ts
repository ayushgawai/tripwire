"use client";
// Attention helpers for the family page: a synthesized chime (no asset), title flash, and
// an OS notification if the viewer granted permission. All best-effort and silent on failure.

let ctx: AudioContext | null = null;

export function unlockAudio(): boolean {
  try {
    ctx ??= new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    if (ctx.state === "suspended") void ctx.resume();
    return true;
  } catch {
    return false;
  }
}

export function chime() {
  if (!ctx) return;
  try {
    const now = ctx.currentTime;
    [880, 660, 880].forEach((f, i) => {
      const o = ctx!.createOscillator();
      const g = ctx!.createGain();
      o.type = "sine";
      o.frequency.value = f;
      g.gain.setValueAtTime(0.0001, now + i * 0.22);
      g.gain.exponentialRampToValueAtTime(0.25, now + i * 0.22 + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.22 + 0.2);
      o.connect(g).connect(ctx!.destination);
      o.start(now + i * 0.22);
      o.stop(now + i * 0.22 + 0.22);
    });
  } catch {
    /* ignore */
  }
}

export async function requestNotify(): Promise<boolean> {
  try {
    if (!("Notification" in window)) return false;
    if (Notification.permission === "granted") return true;
    return (await Notification.requestPermission()) === "granted";
  } catch {
    return false;
  }
}

export function notify(title: string, body: string) {
  try {
    if ("Notification" in window && Notification.permission === "granted" && document.hidden) {
      new Notification(title, { body, tag: "tripwire-alert", requireInteraction: true });
    }
  } catch {
    /* ignore */
  }
}

export function flashTitle(text: string): () => void {
  const original = document.title;
  let on = false;
  const id = setInterval(() => {
    document.title = (on = !on) ? `⚠ ${text}` : original;
  }, 900);
  const stop = () => {
    clearInterval(id);
    document.title = original;
    window.removeEventListener("focus", stop);
  };
  window.addEventListener("focus", stop);
  return stop;
}
