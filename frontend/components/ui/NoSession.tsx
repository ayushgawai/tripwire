import Link from "next/link";
import { Logo } from "./Logo";

export function NoSession({ role }: { role: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col items-center justify-center gap-6 px-6 text-center">
      <Logo />
      <h1 className="font-display text-3xl">No session selected</h1>
      <p className="text-ink-soft">
        Open the {role} page from a session link, or start one from the launcher.
      </p>
      <div className="flex gap-3">
        <Link href="/" className="rounded-2xl bg-ink px-5 py-3 font-semibold text-paper">Open launcher</Link>
        <Link href={`/${role}?replay=1`} className="rounded-2xl border border-line bg-card px-5 py-3 font-semibold">Demo replay</Link>
      </div>
    </main>
  );
}
