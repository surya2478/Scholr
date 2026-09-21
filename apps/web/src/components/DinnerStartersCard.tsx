export type ConversationStarter = {
  icon: string;
  badge: string;
  prompt: string;
  theme?: "orange" | "emerald" | "blue" | "amber";
};

const THEMES = {
  orange: {
    bg: "bg-[#FFFBF5]",
    border: "border-orange-200",
    badge: "text-orange-700",
  },
  emerald: {
    bg: "bg-[#F6FEF9]",
    border: "border-emerald-200",
    badge: "text-emerald-700",
  },
  blue: {
    bg: "bg-[#F5FAFF]",
    border: "border-blue-200",
    badge: "text-blue-700",
  },
  amber: {
    bg: "bg-[#FFFDF5]",
    border: "border-amber-300",
    badge: "text-amber-800",
  },
};

export function DinnerStartersCard({
  studentName = "Student",
  starters,
}: {
  studentName?: string;
  starters?: ConversationStarter[];
}) {
  const defaultStarters: ConversationStarter[] = [
    {
      icon: "📐",
      badge: "Maths Breakthrough",
      theme: "orange",
      prompt: `"${studentName} solved tricky quadratics with negative coefficients on her own today. Ask her: 'How did you figure out that -8 and +3 multiplied to -24 and added to -5?'"`,
    },
    {
      icon: "🌍",
      badge: "Sociology Curiosity",
      theme: "emerald",
      prompt: `"She analyzed snowball sampling in social research. Ask her: 'If you were studying a group that didn't trust outsiders, how would you convince them to talk to you?'"`,
    },
  ];

  const items = starters && starters.length > 0 ? starters : defaultStarters;

  return (
    <div className="bg-white rounded-3xl border-2 border-amber-200/80 p-6 shadow-sm space-y-4">
      <div className="flex items-center gap-3">
        <span className="text-3xl select-none">🍽️</span>
        <div>
          <h3 className="font-fun font-bold text-slate-900 text-lg">Tonight&apos;s Dinner Table Starters</h3>
          <p className="text-xs text-slate-500 font-medium">
            Fun questions based on what {studentName} learned today — celebrate wins with zero nagging!
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
        {items.map((item, idx) => {
          const t = THEMES[item.theme ?? "orange"] ?? THEMES.orange;
          return (
            <div key={idx} className={`${t.bg} border-2 ${t.border} p-4 rounded-2xl space-y-2 shadow-2xs`}>
              <div className="flex items-center gap-2">
                <span className="text-lg">{item.icon}</span>
                <span className={`text-xs font-fun font-bold uppercase tracking-wide ${t.badge}`}>
                  {item.badge}
                </span>
              </div>
              <p className="text-xs text-slate-700 leading-relaxed font-medium">
                {item.prompt}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
