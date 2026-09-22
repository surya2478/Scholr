"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Card, Chip, Empty } from "@/components/ui";
import type { Metacognition, MetacognitionItem } from "@/lib/api";
import { shortDate } from "@/lib/format";

export function CalibrationMatrix({ data }: { data: Metacognition | null | undefined }) {
  const [selectedQuadrant, setSelectedQuadrant] = useState<string | null>("dangerous_blindspot");

  if (!data || data.total_evaluated_with_confidence === 0) {
    return (
      <Card
        title="🧠 Metacognitive Calibration Matrix"
        subtitle="Measures how accurately your confidence matches your exam performance"
        tone="purple"
      >
        <Empty>
          Rate your confidence before submitting answers in Practice Lab to unlock your 4-Quadrant Metacognition Matrix!
        </Empty>
      </Card>
    );
  }

  const q = data.quadrants;
  const filteredItems =
    selectedQuadrant === "all"
      ? data.recent_items
      : data.recent_items.filter((it) => it.quadrant === selectedQuadrant);

  return (
    <Card
      title="🧠 Metacognitive Calibration (Confidence vs. Exam Reality)"
      subtitle="Knowing what you know and catching hidden blindspots before exam day"
      tone="purple"
    >
      <div className="space-y-6">
        {/* Metric Header Bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border border-purple-200 bg-gradient-to-r from-purple-50 via-white to-amber-50 p-4 shadow-2xs">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-xl">🎯</span>
              <span className="font-fun font-bold text-slate-900 text-sm md:text-base">
                Calibration Accuracy: {data.brier_calibration_score}%
              </span>
              <Chip tone={data.brier_calibration_score >= 75 ? "good" : "warn"}>
                {data.calibration_rating}
              </Chip>
            </div>
            <p className="text-xs text-slate-600 font-medium leading-relaxed max-w-xl">
              {data.advice}
            </p>
          </div>
          <div className="flex items-center gap-3 bg-white/90 border border-purple-200/80 px-4 py-2 rounded-xl text-center self-stretch sm:self-auto justify-center">
            <div>
              <div className="text-[11px] font-fun font-bold text-slate-400 uppercase tracking-wider">
                Evaluated
              </div>
              <div className="text-lg font-fun font-extrabold text-purple-900">
                {data.total_evaluated_with_confidence}
              </div>
            </div>
          </div>
        </div>

        {/* The 2x2 Epistemic Matrix */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {/* Top-Left: True Mastery */}
          <button
            type="button"
            onClick={() => setSelectedQuadrant(selectedQuadrant === "true_mastery" ? null : "true_mastery")}
            className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
              selectedQuadrant === "true_mastery"
                ? "border-emerald-500 bg-emerald-50/90 shadow-sm scale-[1.01]"
                : "border-emerald-200/80 bg-[#F6FBF7] hover:border-emerald-400 hover:bg-emerald-50/50"
            }`}
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎯</span>
                <span className="font-fun font-bold text-emerald-950 text-sm">
                  True Mastery
                </span>
              </div>
              <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                {q.true_mastery.count} ({q.true_mastery.percentage}%)
              </span>
            </div>
            <div className="text-[11px] font-semibold text-emerald-800/80 mt-1">
              High Confidence · High Score (≥70%)
            </div>
            <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
              Rock solid. Your confidence correctly anticipated full marks.
            </p>
          </button>

          {/* Top-Right: Dangerous Blindspot */}
          <button
            type="button"
            onClick={() => setSelectedQuadrant(selectedQuadrant === "dangerous_blindspot" ? null : "dangerous_blindspot")}
            className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
              selectedQuadrant === "dangerous_blindspot"
                ? "border-rose-500 bg-rose-50/90 shadow-sm scale-[1.01]"
                : "border-rose-200/90 bg-[#FFF5F5] hover:border-rose-400 hover:bg-rose-50/60"
            }`}
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xl">⚠️</span>
                <span className="font-fun font-bold text-rose-950 text-sm">
                  Dangerous Blindspots
                </span>
              </div>
              <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300">
                {q.dangerous_blindspot.count} ({q.dangerous_blindspot.percentage}%)
              </span>
            </div>
            <div className="text-[11px] font-semibold text-rose-800/80 mt-1">
              High Confidence · Dropped Marks (&lt;70%)
            </div>
            <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
              Epistemic traps! You felt sure, but subtle conditions or accuracy errors lost marks.
            </p>
          </button>

          {/* Bottom-Left: Hesitant Mastery */}
          <button
            type="button"
            onClick={() => setSelectedQuadrant(selectedQuadrant === "hesitant_mastery" ? null : "hesitant_mastery")}
            className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
              selectedQuadrant === "hesitant_mastery"
                ? "border-indigo-500 bg-indigo-50/90 shadow-sm scale-[1.01]"
                : "border-indigo-200/80 bg-[#F8F9FF] hover:border-indigo-400 hover:bg-indigo-50/50"
            }`}
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xl">🌟</span>
                <span className="font-fun font-bold text-indigo-950 text-sm">
                  Hesitant Mastery
                </span>
              </div>
              <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-300">
                {q.hesitant_mastery.count} ({q.hesitant_mastery.percentage}%)
              </span>
            </div>
            <div className="text-[11px] font-semibold text-indigo-800/80 mt-1">
              Low Confidence · High Score (≥70%)
            </div>
            <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
              Underestimated yourself! You scored high despite feeling unsure. Trust your instincts!
            </p>
          </button>

          {/* Bottom-Right: Known Gaps */}
          <button
            type="button"
            onClick={() => setSelectedQuadrant(selectedQuadrant === "known_gap" ? null : "known_gap")}
            className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
              selectedQuadrant === "known_gap"
                ? "border-amber-500 bg-amber-50/90 shadow-sm scale-[1.01]"
                : "border-amber-200/80 bg-[#FFFDF5] hover:border-amber-400 hover:bg-amber-50/50"
            }`}
          >
            <div className="flex items-center justify-between gap-2 w-full">
              <div className="flex items-center gap-2">
                <span className="text-xl">🔍</span>
                <span className="font-fun font-bold text-amber-950 text-sm">
                  Known Gaps
                </span>
              </div>
              <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                {q.known_gap.count} ({q.known_gap.percentage}%)
              </span>
            </div>
            <div className="text-[11px] font-semibold text-amber-800/80 mt-1">
              Low Confidence · Low Score (&lt;70%)
            </div>
            <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
              Healthy self-awareness. You accurately flagged concepts that still need focused revision.
            </p>
          </button>
        </div>

        {/* Selected Quadrant Item Drill-Down */}
        {selectedQuadrant && (
          <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
            <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
              <div className="font-fun font-bold text-xs uppercase tracking-wider text-slate-700">
                {selectedQuadrant === "dangerous_blindspot" && "⚠️ Blindspot Traps to Review"}
                {selectedQuadrant === "true_mastery" && "🎯 Confident & Mastered Questions"}
                {selectedQuadrant === "hesitant_mastery" && "🌟 Hesitant Victories (Trust Your Preparation!)"}
                {selectedQuadrant === "known_gap" && "🔍 Honest Gaps to Practice"}
              </div>
              <span className="text-xs text-slate-400 font-medium">
                Showing {filteredItems.length} recent item{filteredItems.length === 1 ? "" : "s"}
              </span>
            </div>

            {filteredItems.length === 0 ? (
              <p className="text-xs text-slate-500 italic py-2">
                No questions currently in this quadrant.
              </p>
            ) : (
              <div className="space-y-2.5">
                {filteredItems.map((it: MetacognitionItem) => (
                  <div
                    key={it.attempt_id}
                    className="p-3 rounded-xl border border-slate-100 bg-[#FAFAFA] flex flex-col gap-1.5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-fun font-bold text-slate-700">
                          {it.marks_awarded} / {it.marks_available} Marks ({it.percentage}%)
                        </span>
                        <span className="text-slate-300">·</span>
                        <span className="text-slate-500 font-medium">
                          Felt &quot;{it.confidence_label}&quot;
                        </span>
                      </div>
                      <span className="text-[11px] text-slate-400 font-medium">
                        {shortDate(it.submitted_at)}
                      </span>
                    </div>

                    <div className="text-xs font-medium text-slate-800 line-clamp-2">
                      <MathText text={it.question_stem} />
                    </div>

                    {it.mistakes.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {it.mistakes.map((m, idx) => (
                          <span
                            key={idx}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100/90 text-amber-900 text-[11px] font-medium border border-amber-200"
                          >
                            <span>⚠️</span> {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
