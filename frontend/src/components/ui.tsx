import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Sparkle({ className = "", size = 14 }: { className?: string; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M12 2l1.9 6.6L20.5 10.5l-6.6 1.9L12 19l-1.9-6.6L3.5 10.5l6.6-1.9z" fill="currentColor" />
    </svg>
  );
}

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-violet-600 text-white shadow-[var(--shadow-lift)]">
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden="true">
          <path d="M8 22V10l8 7 8-7v12" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <Sparkle className="absolute -top-1 -right-1 text-blush-200" size={12} />
      </span>
      {!compact && (
        <span className="hidden text-[17px] font-semibold tracking-tight text-ink sm:inline">
          Meeting<span className="text-violet-600">Mind</span>
        </span>
      )}
    </span>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50 select-none";
  const sizes = { sm: "h-8 px-3 text-[13px]", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-[15px]" }[size];
  const variants = {
    primary:
      "bg-violet-600 text-white shadow-[0_1px_0_rgb(255_255_255/0.2)_inset,0_6px_16px_-6px_rgb(109_91_208/0.6)] hover:bg-violet-700 active:translate-y-px",
    secondary: "border border-line-strong bg-surface text-ink hover:border-lavender-300 hover:bg-lavender-50",
    ghost: "text-ink-soft hover:bg-lavender-50 hover:text-ink",
    danger: "border border-rose-600/20 bg-rose-50 text-rose-600 hover:bg-rose-600 hover:text-white",
  }[variant];
  return (
    <button ref={ref} className={cx(base, sizes, variants, className)} disabled={disabled || loading} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

type Tone = "violet" | "blush" | "sage" | "amber" | "rose" | "gray";

export function Badge({ tone = "gray", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  const tones: Record<Tone, string> = {
    violet: "bg-lavender-100 text-violet-700",
    blush: "bg-blush-100 text-blush-600",
    sage: "bg-sage-50 text-sage-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
    gray: "bg-mist text-muted border border-line",
  };
  return (
    <span title={title} className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11.5px] font-medium whitespace-nowrap", tones[tone], className)}>
      {children}
    </span>
  );
}

export function SectionHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h2 className="display text-[30px] leading-tight">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-lavender-50 text-violet-500">{icon ?? <Sparkle size={18} />}</div>
      <div className="font-medium text-ink">{title}</div>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}

export function SignalBadge({ signal }: { signal: "strong" | "moderate" | "weak" }) {
  const tone = signal === "strong" ? "sage" : signal === "moderate" ? "violet" : "amber";
  return (
    <Badge tone={tone} title="Extraction signal: how strongly the wording and semantic check agree. A heuristic label, not a probability.">
      {signal} signal
    </Badge>
  );
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 text-[12.5px] text-muted">
        {icon}
        {label}
      </div>
      <div className="mt-1.5 text-[26px] font-semibold tracking-tight text-ink">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-faint">{hint}</div>}
    </div>
  );
}
