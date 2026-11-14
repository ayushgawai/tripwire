import { cn } from "./cn";

export function Logo({ className, compact }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2 brand-logo font-display text-2xl font-normal tracking-tight", className)}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="9" className="fill-champagne" />
        <path d="M5 19h6l3-8 4 12 3-7h6" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="stroke-action-ink" />
        <circle cx="27" cy="16" r="2.2" className="fill-action-ink" />
      </svg>
      {!compact && <span className="brand-wordmark">Tripwire</span>}
    </span>
  );
}
