"use client";
import { cn } from "./cn";

type Variant = "primary" | "danger" | "family" | "ghost" | "outline";
type Size = "sm" | "md" | "lg" | "xl";

const VARIANT: Record<Variant, string> = {
  primary: "bg-ink text-paper hover:opacity-90",
  danger: "bg-danger text-white hover:brightness-110",
  family: "bg-family text-white hover:brightness-110",
  ghost: "bg-transparent text-ink-soft hover:bg-line/60",
  outline: "border border-line bg-card text-ink hover:border-ink-faint",
};
const SIZE: Record<Size, string> = {
  sm: "h-8 px-3 text-xs rounded-lg",
  md: "h-10 px-4 text-sm rounded-xl",
  lg: "h-12 px-6 text-base rounded-2xl",
  xl: "h-16 px-8 text-xl rounded-3xl",
};

export function Button({
  variant = "primary",
  size = "md",
  loading,
  className,
  children,
  disabled,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center gap-2 font-semibold transition",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-family/30",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANT[variant],
        SIZE[size],
        className,
      )}
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}
      {children}
    </button>
  );
}
