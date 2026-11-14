import { cn } from "./cn";

export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-display text-xl font-semibold tracking-tight", className)}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="9" className="fill-ink" />
        <path d="M5 19h6l3-8 4 12 3-7h6" fill="none" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" className="stroke-paper" />
        <circle cx="27" cy="16" r="2.2" className="fill-danger" />
      </svg>
      {!compact && <span>Tripwire</span>}
    </span>
  );
}
