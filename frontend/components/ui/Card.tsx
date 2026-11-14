import { cn } from "./cn";

export function Card({
  className,
  children,
  title,
  aside,
}: {
  className?: string;
  children: React.ReactNode;
  title?: React.ReactNode;
  aside?: React.ReactNode;
}) {
  return (
    <section className={cn("rounded-3xl border border-line bg-card p-5 shadow-[0_1px_0_rgba(0,0,0,0.02)]", className)}>
      {(title || aside) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          {title && (
            <h2 className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-faint">{title}</h2>
          )}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}
