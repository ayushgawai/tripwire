"use client";
// One-click live demo control: fresh session + reuse the same Presenter and Family windows.
import { useState } from "react";

const BACKEND = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

export default function DemoControl() {
  const [status, setStatus] = useState("Ready. Arrange the two windows side by side after the first click.");
  const start = async (scenario: "scam" | "fall") => {
    const presenterWin = window.open("about:blank", "tw-presenter");
    const familyWin = window.open("about:blank", "tw-family");
    setStatus("Starting…");
    try {
      const r = await fetch(`${BACKEND}/api/demo/start`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario }) });
      const d = await r.json();
      presenterWin?.location.replace(d.presenter);
      familyWin?.location.replace(d.family);
      setStatus(scenario === "scam"
        ? "Scam call is live. The laptop is listening. Start talking in about 5 seconds."
        : "Fall detection is live. Drop the band onto a cushion.");
    } catch {
      setStatus("Could not reach the backend on :8000.");
    }
  };
  const btn = "w-full rounded-3xl px-8 py-10 text-left shadow-lg transition hover:-translate-y-0.5 focus:outline-none focus-visible:ring-4";
  return (
    <main className="min-h-screen bg-[#F1F1EF] px-6 py-12 text-[#1F2023]">
      <div className="mx-auto max-w-xl space-y-6">
        <h1 className="font-display text-5xl">Tripwire live demo</h1>
        <button className={`${btn} bg-[#1F2023] text-white focus-visible:ring-[#E5384F]/40`} onClick={() => start("scam")}>
          <span className="block text-sm font-semibold uppercase tracking-widest text-white/60">Scene 1</span>
          <span className="mt-1 block text-3xl font-semibold">Scam call</span>
          <span className="mt-2 block text-white/70">AI holds the caller, family joins in one tap</span>
        </button>
        <button className={`${btn} bg-white focus-visible:ring-[#3B4FD8]/30`} onClick={() => start("fall")}>
          <span className="block text-sm font-semibold uppercase tracking-widest text-[#7A7E85]">Scene 2</span>
          <span className="mt-1 block text-3xl font-semibold">Fall detection</span>
          <span className="mt-2 block text-[#4A4E54]">Drop the band, family is alerted instantly</span>
        </button>
        <p className="rounded-2xl bg-white px-5 py-4 text-lg" role="status">{status}</p>
        <p className="text-sm text-[#7A7E85]">Click a scene again any time to reset it.</p>
      </div>
    </main>
  );
}
