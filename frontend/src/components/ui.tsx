import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2, Moon, Sun } from "lucide-react";
import { useTheme } from "../state/theme";

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
      <span className="relative grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-violet-400 via-violet-500 to-violet-800 text-white shadow-[var(--shadow-glow)]">
        <svg viewBox="0 0 32 32" className="h-5 w-5" aria-hidden="true">
          <path d="M8 22V10l8 7 8-7v12" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <Sparkle className="absolute -top-1 -right-1 text-lime-400" size={12} />
      </span>
      {!compact && (
        <span className="hidden font-[family-name:var(--font-display)] text-[18px] font-bold tracking-[-0.03em] text-ink sm:inline">
          Meeting<span className="text-gradient">Mind</span>
        </span>
      )}
    </span>
  );
}

/** Sun/moon pill that flips the whole app between the dark and light palettes. */
export function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useTheme();
  const isLight = theme === "light";
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isLight}
      aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
      title={isLight ? "Switch to dark mode" : "Switch to light mode"}
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className={cx(
        "group relative grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-full border border-line-strong bg-wash-2 text-ink-soft transition hover:border-violet-500 hover:text-ink",
        className,
      )}
    >
      <Sun
        className={cx(
          "theme-toggle-icon absolute h-4 w-4",
          isLight ? "rotate-0 scale-100 text-lime-400 opacity-100" : "rotate-90 scale-50 opacity-0",
        )}
      />
      <Moon
        className={cx(
          "theme-toggle-icon absolute h-4 w-4",
          isLight ? "-rotate-90 scale-50 opacity-0" : "rotate-0 scale-100 text-violet-400 opacity-100",
        )}
      />
    </button>
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
      "bg-gradient-to-b from-violet-500 to-violet-800 text-white shadow-[var(--shadow-glow)] hover:brightness-115 active:translate-y-px",
    secondary:
      "border border-line-strong bg-wash-2 text-ink backdrop-blur hover:border-violet-500 hover:shadow-[0_0_12px_rgb(139_92_246/0.25)]",
    ghost: "text-ink-soft hover:bg-wash-3 hover:text-ink",
    danger: "border border-rose-600/20 bg-rose-50 text-rose-600 hover:bg-rose-600 hover:text-white",
  }[variant];
  return (
    <button ref={ref} className={cx(base, sizes, variants, className)} disabled={disabled || loading} {...rest}>
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      {children}
    </button>
  );
});

type Tone = "violet" | "blush" | "sage" | "amber" | "rose" | "lime" | "gray";

export function Badge({ tone = "gray", children, className, title }: { tone?: Tone; children: ReactNode; className?: string; title?: string }) {
  const tones: Record<Tone, string> = {
    violet: "bg-lavender-100 text-violet-300 border-lavender-200",
    blush: "bg-blush-100 text-blush-400 border-blush-200/50",
    sage: "bg-sage-50 text-sage-600 border-sage-600/30",
    amber: "bg-amber-50 text-amber-600 border-amber-600/30",
    rose: "bg-rose-50 text-rose-600 border-rose-600/30",
    lime: "bg-lime-50 text-lime-400 border-lime-300",
    gray: "bg-wash-1 text-muted border-line-strong",
  };
  return (
    <span
      title={title}
      className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[10.5px] font-medium tracking-[0.02em] whitespace-nowrap", tones[tone], className)}
    >
      {children}
    </span>
  );
}

export function SectionHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h2 className="display text-[28px] leading-tight sm:text-[32px]">{title}</h2>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 grid h-12 w-12 place-items-center rounded-2xl border border-lavender-200 bg-lavender-50 text-violet-400">{icon ?? <Sparkle size={18} />}</div>
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

const ACCENT = {
  violet: { text: "text-ink", bar: "bg-violet-500" },
  lime: { text: "text-lime-400", bar: "bg-lime-400" },
  rose: { text: "text-rose-600", bar: "bg-rose-600" },
  amber: { text: "text-amber-600", bar: "bg-amber-600" },
  plain: { text: "text-ink", bar: "bg-wash-4" },
} as const;

export function Stat({
  label,
  value,
  hint,
  icon,
  accent = "plain",
  meter,
  onClick,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  accent?: keyof typeof ACCENT;
  /** 0–1: draws a thin progress meter under the value. */
  meter?: number;
  onClick?: () => void;
}) {
  const a = ACCENT[accent];
  const Tag = onClick ? "button" : "div";
  return (
    <Tag onClick={onClick} className={cx("card flex flex-col p-4 text-left", onClick && "card-hover cursor-pointer")}>
      <div className="flex items-start justify-between gap-2">
        <span className="font-mono text-[10.5px] tracking-[0.1em] text-muted uppercase">{label}</span>
        {icon && <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg border border-line bg-wash-1">{icon}</span>}
      </div>
      <div className={cx("mt-2 font-[family-name:var(--font-display)] text-[34px] leading-none font-bold tracking-[-0.04em] tabular-nums", a.text)}>{value}</div>
      {hint && <div className="mt-2 font-mono text-[11px] text-faint">{hint}</div>}
      {meter !== undefined && (
        <div className="mt-auto pt-3">
          <div className="h-1 overflow-hidden rounded-full bg-wash-2">
            <div className={cx("h-full rounded-full", a.bar)} style={{ width: `${Math.round(Math.max(0, Math.min(1, meter)) * 100)}%` }} />
          </div>
        </div>
      )}
    </Tag>
  );
}

/** Decorative animated bars; purely visual, hidden from assistive tech. */
export function Waveform({ bars = 12, className = "", height = 22 }: { bars?: number; className?: string; height?: number }) {
  const colors = ["bg-violet-400", "bg-lime-400", "bg-sage-600", "bg-violet-300"];
  return (
    <span aria-hidden="true" className={cx("wave inline-flex items-center gap-[3px]", className)} style={{ height }}>
      {Array.from({ length: bars }, (_, i) => (
        <span
          key={i}
          className={colors[i % colors.length]}
          style={{ height: `${40 + ((i * 37) % 60)}%`, animationDelay: `${(i * 0.13) % 1.1}s` }}
        />
      ))}
    </span>
  );
}
