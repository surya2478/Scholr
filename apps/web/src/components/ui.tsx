import Link from "next/link";

const CARD_TONES = {
  default: "bg-white border border-slate-200/90 shadow-xs hover:shadow-md",
  orange: "bg-white border border-blue-200/90 shadow-xs hover:shadow-md",
  emerald: "bg-white border border-emerald-200/90 shadow-xs hover:shadow-md",
  blue: "bg-white border border-blue-200/90 shadow-xs hover:shadow-md",
  amber: "bg-white border border-slate-200/90 shadow-xs hover:shadow-md",
  purple: "bg-white border border-indigo-200/90 shadow-xs hover:shadow-md",
} as const;

const ACCENT_DOT = {
  default: "bg-blue-600",
  orange: "bg-blue-600",
  emerald: "bg-emerald-500",
  blue: "bg-blue-600",
  amber: "bg-amber-500",
  purple: "bg-indigo-600",
} as const;

export function Card({
  title,
  subtitle,
  action,
  tone = "default",
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  action?: { href: string; label: string };
  tone?: keyof typeof CARD_TONES;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-2xl p-5 md:p-6 transition-all flex flex-col gap-4 ${CARD_TONES[tone]} ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex flex-col gap-0.5">
            {title && (
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${ACCENT_DOT[tone]}`} />
                <h2 className="text-base md:text-lg font-extrabold text-slate-900 tracking-tight">{title}</h2>
              </div>
            )}
            {subtitle && <p className="text-xs text-slate-500 font-medium pl-4">{subtitle}</p>}
          </div>
          {action && (
            <Link
              href={action.href}
              className="ml-auto inline-flex items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-xl border border-blue-200 transition-all"
            >
              <span>{action.label}</span>
              <span>→</span>
            </Link>
          )}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({
  label,
  value,
  hint,
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: string;
}) {
  return (
    <div className="flex min-h-[76px] flex-col justify-center gap-1 rounded-2xl bg-white border border-slate-200/90 p-4 shadow-2xs hover:border-blue-300 transition-colors">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-slate-400">{label}</span>
        {icon && <span className="text-base">{icon}</span>}
      </div>
      <span className="font-mono text-lg font-extrabold text-slate-900">{value}</span>
      {hint && <span className="text-[11px] text-slate-500 font-medium">{hint}</span>}
    </div>
  );
}

const TONES = {
  good: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warn: "bg-amber-50 text-amber-900 border-amber-300",
  brand: "bg-blue-50 text-blue-800 border-blue-200",
  alert: "bg-rose-50 text-rose-800 border-rose-200",
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
} as const;

export function Chip({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: React.ReactNode }) {
  return <span className={`chip ${TONES[tone]} shadow-2xs`}>{children}</span>;
}

export function LevelBar({ level }: { level: number }) {
  return (
    <div className="flex w-28 gap-1 items-center" aria-hidden>
      {[1, 2, 3, 4, 5].map((n) => (
        <div
          key={n}
          className={`h-2 flex-1 rounded-full transition-all ${
            n <= level
              ? "bg-gradient-to-r from-blue-600 to-emerald-500 shadow-xs"
              : "bg-slate-200"
          }`}
        />
      ))}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/70 px-5 py-7 text-center">
      <div className="text-xl mb-1.5 select-none">📊</div>
      <p className="text-sm font-medium text-slate-600">{children}</p>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-800 flex items-start gap-2.5">
      <span className="text-lg leading-none">⚠️</span>
      <div className="flex-1 font-medium">{message}</div>
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "emerald";
}) {
  const styles = {
    primary:
      "bg-gradient-to-r from-[#1E40AF] to-[#2563EB] hover:from-[#1E3A8A] hover:to-[#1D4ED8] text-white shadow-sm shadow-blue-600/20 font-bold disabled:opacity-50",
    secondary:
      "border border-slate-300 bg-white text-slate-800 hover:bg-slate-50 hover:border-slate-400 font-semibold shadow-2xs disabled:opacity-50",
    ghost:
      "text-blue-600 hover:bg-blue-50 font-semibold disabled:opacity-50",
    emerald:
      "bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white shadow-sm shadow-emerald-600/20 font-bold disabled:opacity-50",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-xs md:text-sm transition-all cursor-pointer select-none ${styles} ${props.className ?? ""}`}
    >
      {children}
    </button>
  );
}
