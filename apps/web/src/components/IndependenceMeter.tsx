"use client";

import { Card, Chip } from "@/components/ui";

type IndependenceData = {
  independence_index: number;
  tier: string;
  unassisted_count: number;
  nudged_count: number;
  assisted_count: number;
  total: number;
  advice: string;
};

export function IndependenceMeter({ data }: { data: IndependenceData | undefined }) {
  if (!data || data.total === 0) {
    return (
      <Card
        title="🦅 Socratic Independence Index"
        subtitle="Measuring learning autonomy over AI dependency"
        tone="blue"
      >
        <p className="text-xs text-slate-500 italic">
          Complete practice questions in the Lab to measure your learning independence.
        </p>
      </Card>
    );
  }

  const unassistedPct = Math.round((data.unassisted_count / data.total) * 100);
  const nudgedPct = Math.round((data.nudged_count / data.total) * 100);
  const assistedPct = Math.round((data.assisted_count / data.total) * 100);

  return (
    <Card
      title="🦅 Socratic Independence Index (Anti-AI Dependency)"
      subtitle="AI should build your independent strength, not become an exam crutch"
      tone="blue"
    >
      <div className="space-y-4">
        {/* Metric Header Bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border border-blue-200 bg-gradient-to-r from-blue-50 via-white to-indigo-50 p-4 shadow-2xs">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🦅</span>
              <span className="font-fun font-bold text-slate-900 text-base">
                Independence Index: {data.independence_index}%
              </span>
              <Chip tone={data.independence_index >= 70 ? "good" : "brand"}>
                {data.tier}
              </Chip>
            </div>
            <p className="text-xs text-slate-600 font-medium max-w-xl leading-relaxed">
              {data.advice}
            </p>
          </div>
          <div className="flex items-center gap-3 bg-white/90 border border-blue-200/80 px-4 py-2 rounded-xl text-center self-stretch sm:self-auto justify-center">
            <div>
              <div className="text-[10.5px] font-fun font-bold text-slate-400 uppercase tracking-wider">
                Unassisted
              </div>
              <div className="text-lg font-fun font-extrabold text-blue-950">
                {data.unassisted_count} / {data.total}
              </div>
            </div>
          </div>
        </div>

        {/* Visual Stacked Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-xs font-semibold text-slate-600">
            <span>Autonomous Solving Distribution</span>
            <span>{data.total} Marked Questions</span>
          </div>

          <div className="h-4 w-full overflow-hidden rounded-full bg-slate-100 flex shadow-inner">
            <div
              className="h-full bg-emerald-500 transition-all duration-500"
              style={{ width: `${unassistedPct}%` }}
              title={`Level 0 (Zero Help): ${unassistedPct}%`}
            />
            <div
              className="h-full bg-amber-400 transition-all duration-500"
              style={{ width: `${nudgedPct}%` }}
              title={`Level 1 (Nudge Only): ${nudgedPct}%`}
            />
            <div
              className="h-full bg-slate-300 transition-all duration-500"
              style={{ width: `${assistedPct}%` }}
              title={`Level 2-5 (Hints/Solution): ${assistedPct}%`}
            />
          </div>

          {/* Legend */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-xs">
            <div className="flex items-center gap-2 p-2 rounded-xl bg-emerald-50/70 border border-emerald-200/60">
              <span className="h-3 w-3 rounded-full bg-emerald-500 flex-none" />
              <div>
                <span className="font-fun font-bold text-emerald-950 block text-[11px]">
                  Zero AI Help (L0): {data.unassisted_count} ({unassistedPct}%)
                </span>
                <span className="text-[10px] text-slate-500">True Exam Simulation</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2 rounded-xl bg-amber-50/70 border border-slate-200/80">
              <span className="h-3 w-3 rounded-full bg-amber-400 flex-none" />
              <div>
                <span className="font-fun font-bold text-amber-950 block text-[11px]">
                  Nudge Only (L1): {data.nudged_count} ({nudgedPct}%)
                </span>
                <span className="text-[10px] text-slate-500">Minimal Scaffolding</span>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2 rounded-xl bg-slate-50 border border-slate-200">
              <span className="h-3 w-3 rounded-full bg-slate-400 flex-none" />
              <div>
                <span className="font-fun font-bold text-slate-800 block text-[11px]">
                  Guided Hints (L2-5): {data.assisted_count} ({assistedPct}%)
                </span>
                <span className="text-[10px] text-slate-500">Coached Learning</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
