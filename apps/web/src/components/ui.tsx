import Link from "next/link";

const CARD_TONES = {
  default: "bg-white border-2 border-amber-200/80 shadow-sm hover:shadow-md",
  orange: "bg-[#FFFAF5] border-2 border-orange-200 shadow-sm hover:shadow-md",
  emerald: "bg-[#F6FEF9] border-2 border-emerald-200 shadow-sm hover:shadow-md",
  blue: "bg-[#F5FAFF] border-2 border-blue-200 shadow-sm hover:shadow-md",
  amber: "bg-[#FFFDF5] border-2 border-amber-300/80 shadow-sm hover:shadow-md",
  purple: "bg-[#FAF7FF] border-2 border-purple-200 shadow-sm hover:shadow-md",
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
    <section className={`rounded-3xl p-5 md:p-6 transition-all flex flex-col gap-3.5 ${CARD_TONES[tone]} ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3">
          <div className="flex flex-col gap-0.5">
            {title && <h2 className="text-lg font-fun font-bold text-slate-900 tracking-tight">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-500 font-medium">{subtitle}</p>}
          </div>
          {action && (
            <Link
              href={action.href}
              className="ml-auto inline-flex items-center gap-1 text-xs font-fun font-bold text-orange-600 hover:text-orange-700 bg-orange-50 hover:bg-orange-100 px-3 py-1.5 rounded-xl border border-orange-200 transition-all hover:scale-105"
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
    <div className="flex min-h-[72px] flex-col justify-center gap-1 rounded-2xl bg-[#FFFDF9] border border-amber-200/60 p-4 shadow-2xs hover:border-amber-300 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500">{label}</span>
        {icon && <span className="text-base">{icon}</span>}
      </div>
      <span className="text-base font-fun font-bold text-slate-900">{value}</span>
      {hint && <span className="text-[11px] text-slate-400 font-medium">{hint}</span>}
    </div>
  );
}

const TONES = {
  good: "bg-emerald-50 text-emerald-800 border-emerald-200",
  warn: "bg-amber-50 text-amber-900 border-amber-300",
  brand: "bg-orange-50 text-orange-800 border-orange-200",
  alert: "bg-rose-50 text-rose-800 border-rose-200",
  neutral: "bg-slate-100/80 text-slate-700 border-slate-200",
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
              ? "bg-gradient-to-r from-orange-400 to-amber-500 shadow-xs"
              : "bg-slate-200/80"
          }`}
        />
      ))}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-amber-200/80 bg-amber-50/30 px-5 py-7 text-center">
      <div className="text-2xl mb-1.5 select-none">🌱</div>
      <p className="text-sm font-medium text-slate-600">{children}</p>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <div className="rounded-2xl border-2 border-rose-200 bg-rose-50/90 p-4 text-sm text-rose-800 flex items-start gap-2.5">
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
      "bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white shadow-md shadow-orange-500/20 font-fun font-bold hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100",
    secondary:
      "border-2 border-orange-200 bg-white text-slate-700 hover:bg-orange-50/50 hover:border-orange-300 font-semibold shadow-2xs hover:scale-102 active:scale-98 disabled:opacity-50 disabled:hover:scale-100",
    ghost:
      "text-orange-600 hover:bg-orange-100/60 font-semibold disabled:opacity-50",
    emerald:
      "bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-700 hover:to-teal-600 text-white shadow-md shadow-emerald-500/20 font-fun font-bold hover:scale-105 active:scale-95 disabled:opacity-50 disabled:hover:scale-100",
  }[variant];
  return (
    <button
      {...props}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-2xl px-5 text-sm transition-all cursor-pointer select-none ${styles} ${props.className ?? ""}`}
    >
      {children}
    </button>
  );
}
