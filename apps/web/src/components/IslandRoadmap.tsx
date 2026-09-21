import Link from "next/link";

export type IslandStep = {
  id: string;
  title: string;
  status: "mastered" | "active" | "next" | "locked";
  code?: string;
  tag?: string;
};

export function IslandRoadmap({
  studentName = "Student",
  steps,
}: {
  studentName?: string;
  steps?: IslandStep[];
}) {
  // Default steps if none provided (or fallback to Cambridge curriculum topics)
  const defaultSteps: IslandStep[] = [
    {
      id: "1",
      title: "Numbers & Indices",
      status: "mastered",
      code: "CIE 1.1",
      tag: "Mastered ✓",
    },
    {
      id: "2",
      title: "Linear Graphs",
      status: "mastered",
      code: "CIE 2.2",
      tag: "Mastered ✓",
    },
    {
      id: "3",
      title: "Quadratics",
      status: "active",
      code: "Topic E2.5",
      tag: "You are here! ⭐",
    },
    {
      id: "4",
      title: "Geometry Angles",
      status: "next",
      code: "CIE 3.1",
      tag: "Next Up",
    },
    {
      id: "5",
      title: "Term 1 Quest",
      status: "locked",
      code: "Paper 2 Form A",
      tag: "Milestone",
    },
  ];

  const currentSteps = steps && steps.length > 0 ? steps : defaultSteps;
  const masteredCount = currentSteps.filter((s) => s.status === "mastered").length;
  const activeCount = currentSteps.filter((s) => s.status === "active").length;

  return (
    <div className="bg-white rounded-3xl border-2 border-amber-200/80 p-6 shadow-sm hover:shadow-md transition-all">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-fun font-bold text-slate-900 flex items-center gap-2">
            <span>🗺️</span>
            <span>{studentName}&apos;s Term 1 Island Map</span>
          </h3>
          <p className="text-xs text-slate-500 font-medium">
            Every topic conquered unlocks the next learning island!
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-semibold">
          <span className="h-3 w-3 rounded-full bg-emerald-500"></span>
          <span className="text-slate-600">{masteredCount} Conquered</span>
          <span className="h-3 w-3 rounded-full bg-amber-400 ml-2"></span>
          <span className="text-slate-600">{activeCount} In Progress</span>
        </div>
      </div>

      {/* Visual Step Path */}
      <div className="relative py-4 overflow-x-auto">
        <div className="min-w-[620px] flex items-center justify-between relative px-6">
          {/* Background Connecting Line */}
          <div className="absolute left-10 right-10 top-1/2 -translate-y-1/2 h-3 bg-amber-100 rounded-full z-0"></div>
          <div
            className="absolute left-10 top-1/2 -translate-y-1/2 h-3 bg-gradient-to-r from-emerald-400 via-amber-400 to-orange-400 rounded-full z-0"
            style={{
              width: `${Math.min(
                100,
                Math.max(20, ((masteredCount + (activeCount ? 0.5 : 0)) / currentSteps.length) * 100),
              )}%`,
            }}
          ></div>

          {currentSteps.map((step) => {
            if (step.status === "mastered") {
              return (
                <div key={step.id} className="relative z-10 flex flex-col items-center">
                  <div className="h-12 w-12 rounded-2xl bg-emerald-500 text-white flex items-center justify-center text-xl shadow-md border-4 border-white font-bold transition-transform hover:scale-110 cursor-default">
                    ✓
                  </div>
                  <span className="text-xs font-bold text-slate-800 mt-2 text-center max-w-[100px] truncate">
                    {step.title}
                  </span>
                  <span className="text-[10px] text-emerald-600 font-semibold">{step.tag ?? "Mastered"}</span>
                </div>
              );
            }

            if (step.status === "active") {
              return (
                <div key={step.id} className="relative z-10 flex flex-col items-center">
                  <Link href="/student/practice">
                    <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-orange-500 to-amber-400 text-white flex items-center justify-center text-2xl shadow-lg border-4 border-white font-bold animate-bounce ring-4 ring-orange-200 cursor-pointer hover:scale-110 transition-transform">
                      ⭐
                    </div>
                  </Link>
                  <span className="text-xs font-bold text-orange-600 mt-1 text-center max-w-[110px] truncate">
                    {step.title}
                  </span>
                  <span className="text-[10px] bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-bold mt-0.5">
                    {step.tag ?? "Active!"}
                  </span>
                </div>
              );
            }

            return (
              <div key={step.id} className="relative z-10 flex flex-col items-center opacity-70">
                <div className="h-12 w-12 rounded-2xl bg-slate-200 text-slate-500 flex items-center justify-center text-lg border-4 border-white font-bold">
                  {step.status === "next" ? "🔒" : "🏆"}
                </div>
                <span className="text-xs font-medium text-slate-600 mt-2 text-center max-w-[100px] truncate">
                  {step.title}
                </span>
                <span className="text-[10px] text-slate-400 font-medium">{step.tag ?? "Upcoming"}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
