import Link from "next/link";

export type SubjectCardTheme = "maths" | "sociology" | "iit" | "default";

const THEMES: Record<
  SubjectCardTheme,
  {
    bg: string;
    border: string;
    gradient: string;
    badgeBg: string;
    badgeText: string;
    buttonGradient: string;
    buttonHover: string;
    shadow: string;
    checkColor: string;
  }
> = {
  maths: {
    bg: "bg-[#FFFAF5]",
    border: "border-orange-200/90",
    gradient: "from-orange-400 via-amber-400 to-yellow-300",
    badgeBg: "bg-white/90",
    badgeText: "text-orange-700",
    buttonGradient: "from-orange-500 to-amber-500",
    buttonHover: "hover:from-orange-600 hover:to-amber-600",
    shadow: "shadow-orange-500/20",
    checkColor: "text-orange-500",
  },
  sociology: {
    bg: "bg-[#F6FEF9]",
    border: "border-emerald-200/90",
    gradient: "from-emerald-400 via-teal-400 to-cyan-300",
    badgeBg: "bg-white/90",
    badgeText: "text-emerald-700",
    buttonGradient: "from-emerald-600 to-teal-500",
    buttonHover: "hover:from-emerald-700 hover:to-teal-600",
    shadow: "shadow-emerald-500/20",
    checkColor: "text-emerald-600",
  },
  iit: {
    bg: "bg-[#F5FAFF]",
    border: "border-blue-200/90",
    gradient: "from-indigo-400 via-blue-400 to-sky-300",
    badgeBg: "bg-white/90",
    badgeText: "text-blue-700",
    buttonGradient: "from-blue-600 to-indigo-500",
    buttonHover: "hover:from-blue-700 hover:to-indigo-600",
    shadow: "shadow-blue-500/20",
    checkColor: "text-blue-600",
  },
  default: {
    bg: "bg-white",
    border: "border-amber-200/90",
    gradient: "from-amber-400 via-orange-400 to-amber-300",
    badgeBg: "bg-white/90",
    badgeText: "text-amber-800",
    buttonGradient: "from-orange-500 to-amber-500",
    buttonHover: "hover:from-orange-600 hover:to-amber-600",
    shadow: "shadow-orange-500/20",
    checkColor: "text-orange-500",
  },
};

export function SubjectProgramCard({
  theme = "default",
  icon,
  codeBadge,
  topicsReadyBadge,
  title,
  description,
  bullets,
  buttonText,
  buttonHref,
}: {
  theme?: SubjectCardTheme;
  icon: string;
  codeBadge?: string;
  topicsReadyBadge?: string;
  title: string;
  description: string;
  bullets?: { label: string; value: string }[];
  buttonText: string;
  buttonHref: string;
}) {
  const t = THEMES[theme] ?? THEMES.default;

  return (
    <div
      className={`${t.bg} border-2 ${t.border} rounded-3xl p-5 shadow-sm hover:shadow-md transition-all flex flex-col justify-between group hover:-translate-y-1`}
    >
      <div className="space-y-3">
        {/* Banner Graphic */}
        <div
          className={`h-36 rounded-2xl bg-gradient-to-br ${t.gradient} relative overflow-hidden flex items-center justify-center p-4 select-none`}
        >
          <span className="text-6xl animate-float">{icon}</span>
          {codeBadge && (
            <span
              className={`absolute top-2.5 left-2.5 ${t.badgeBg} ${t.badgeText} text-[10px] font-bold px-2.5 py-0.5 rounded-lg uppercase tracking-wider shadow-2xs`}
            >
              {codeBadge}
            </span>
          )}
          {topicsReadyBadge && (
            <span className="absolute bottom-2.5 right-2.5 bg-slate-900/80 text-white text-[10px] font-bold px-2.5 py-0.5 rounded-lg shadow-2xs">
              {topicsReadyBadge}
            </span>
          )}
        </div>

        <div>
          <h3 className="text-lg font-fun font-bold text-slate-900 group-hover:text-orange-600 transition-colors">
            {title}
          </h3>
          <p className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
            {description}
          </p>
        </div>

        {bullets && bullets.length > 0 && (
          <div className="space-y-1.5 text-xs text-slate-600 pt-2 border-t border-slate-100">
            {bullets.map((b, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className={`${t.checkColor} font-bold flex-none`}>✓</span>
                <span className="min-w-0">
                  <strong className="font-semibold text-slate-700">{b.label}: </strong>
                  <span>{b.value}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <Link
        href={buttonHref}
        className={`mt-4 w-full py-2.5 rounded-2xl bg-gradient-to-r ${t.buttonGradient} ${t.buttonHover} text-white font-fun font-bold text-sm shadow-md ${t.shadow} transition-all flex items-center justify-center gap-2 hover:scale-102 active:scale-98`}
      >
        <span>{buttonText}</span>
        <span>→</span>
      </Link>
    </div>
  );
}
