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
    <section className={cn("surface-card rounded-[20px] border border-line bg-card p-5", className)}>
      {(title || aside) && (
        <header className="mb-3 flex items-center justify-between gap-3">
          {title && (
            <h2 className="text-xs font-medium tracking-wide text-ink-soft">{title}</h2>
          )}
          {aside}
        </header>
      )}
      {children}
    </section>
  );
}
