"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Card, Chip, Empty } from "@/components/ui";
import type { Metacognition, MetacognitionItem } from "@/lib/api";
import { shortDate } from "@/lib/format";

type MatrixMode = "epistemic" | "velocity";

export function CalibrationMatrix({ data }: { data: Metacognition | null | undefined }) {
  const [mode, setMode] = useState<MatrixMode>("epistemic");
  const [selectedEpistemic, setSelectedEpistemic] = useState<string | null>("dangerous_blindspot");
  const [selectedVelocity, setSelectedVelocity] = useState<string | null>("speed_trap");

  if (!data || data.total_evaluated_with_confidence === 0) {
    return (
      <Card
        title="🧠 Metacognitive & Behavioral Diagnostics"
        subtitle="How sure you were against how you scored, and your time against the time your exam allows"
        tone="purple"
      >
        <Empty>
          Rate how sure you are before you submit answers in Practice, and this will fill in.
        </Empty>
      </Card>
    );
  }

  const q = data.quadrants;
  const v = data.velocity;

  const filteredItems =
    mode === "epistemic"
      ? selectedEpistemic === "all"
        ? data.recent_items
        : data.recent_items.filter((it) => it.quadrant === selectedEpistemic)
      : selectedVelocity === "all"
        ? data.recent_items
        : data.recent_items.filter((it) => it.velocity_category === selectedVelocity);

  return (
    <Card
      title="🧠 Confidence and timing"
      subtitle="Knowing what you know, and how your time compares with the time your exam allows"
      tone="purple"
    >
      <div className="space-y-6">
        {/* Mode Selector Tabs */}
        <div className="flex items-center gap-2 p-1 bg-slate-100/80 rounded-xl w-fit border border-slate-200">
          <button
            type="button"
            onClick={() => setMode("epistemic")}
            className={`px-3.5 py-1.5 text-xs font-fun font-bold rounded-lg transition-all cursor-pointer ${
              mode === "epistemic"
                ? "bg-white text-purple-900 shadow-2xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            🧠 Epistemic Calibration (Confidence vs Reality)
          </button>
          <button
            type="button"
            onClick={() => setMode("velocity")}
            className={`px-3.5 py-1.5 text-xs font-fun font-bold rounded-lg transition-all cursor-pointer ${
              mode === "velocity"
                ? "bg-white text-purple-900 shadow-2xs"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            ⏱ Time against marks
          </button>
        </div>

        {/* Header Metric Bar */}
        {mode === "epistemic" ? (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border border-purple-200 bg-gradient-to-r from-purple-50 via-white to-amber-50 p-4 shadow-2xs">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xl">🎯</span>
                <span className="font-fun font-bold text-slate-900 text-sm md:text-base">
                  How well your confidence matched your marks:{" "}
                  {data.brier_calibration_score === null ? "not enough answers yet" : `${data.brier_calibration_score}%`}
                </span>
                <Chip tone={data.brier_calibration_score !== null && data.brier_calibration_score >= 75 ? "good" : "warn"}>
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
        ) : (
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-2xl border border-cyan-200 bg-gradient-to-r from-cyan-50 via-white to-sky-50 p-4 shadow-2xs">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-xl">⚡</span>
                <span className="font-fun font-bold text-slate-900 text-sm md:text-base">
                  Time used: {v?.exam_time_used_percent != null ? `${v.exam_time_used_percent}% of exam time` : "not timed yet"}
                </span>
                {v?.exam_time_used_percent != null && (
                  <Chip tone={v.exam_time_used_percent <= 100 ? "good" : "warn"}>
                    {v.exam_time_used_percent <= 100 ? "Within exam time" : "Over exam time"}
                  </Chip>
                )}
              </div>
              <p className="text-xs text-slate-600 font-medium leading-relaxed max-w-xl">
                {v?.diagnosis ?? "Answer a few questions and your timing will show here."}
              </p>
            </div>
            <div className="flex items-center gap-4 bg-white/90 border border-cyan-200/80 px-4 py-2 rounded-xl text-center self-stretch sm:self-auto justify-center">
              <div>
                <div className="text-[11px] font-fun font-bold text-slate-400 uppercase tracking-wider">
                  Right, in time
                </div>
                <div className="text-lg font-fun font-extrabold text-emerald-600">
                  {v ? v.optimal_flow_count : 0}
                </div>
              </div>
              <div className="border-l border-slate-200 pl-4">
                <div className="text-[11px] font-fun font-bold text-slate-400 uppercase tracking-wider">
                  Marks lost
                </div>
                <div className="text-lg font-fun font-extrabold text-rose-600">
                  {v ? v.speed_trap_count + v.time_sink_count : 0}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Epistemic 2x2 Grid */}
        {mode === "epistemic" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* Top-Left: True Mastery */}
            <button
              type="button"
              onClick={() => setSelectedEpistemic(selectedEpistemic === "true_mastery" ? null : "true_mastery")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedEpistemic === "true_mastery"
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
              onClick={() => setSelectedEpistemic(selectedEpistemic === "dangerous_blindspot" ? null : "dangerous_blindspot")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedEpistemic === "dangerous_blindspot"
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
              onClick={() => setSelectedEpistemic(selectedEpistemic === "hesitant_mastery" ? null : "hesitant_mastery")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedEpistemic === "hesitant_mastery"
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
              onClick={() => setSelectedEpistemic(selectedEpistemic === "known_gap" ? null : "known_gap")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedEpistemic === "known_gap"
                  ? "border-amber-500 bg-amber-50/90 shadow-sm scale-[1.01]"
                  : "border-slate-200/90 bg-[#FFFDF5] hover:border-amber-400 hover:bg-amber-50/50"
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
        )}

        {/* Time against marks: 2x2 grid */}
        {mode === "velocity" && v && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {/* Optimal Flow */}
            <button
              type="button"
              onClick={() => setSelectedVelocity(selectedVelocity === "optimal_flow" ? null : "optimal_flow")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedVelocity === "optimal_flow"
                  ? "border-emerald-500 bg-emerald-50/90 shadow-sm scale-[1.01]"
                  : "border-emerald-200/80 bg-[#F6FBF7] hover:border-emerald-400 hover:bg-emerald-50/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🟢</span>
                  <span className="font-fun font-bold text-emerald-950 text-sm">
                    Right, in time
                  </span>
                </div>
                <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
                  {v.quadrants.optimal_flow.count} ({v.quadrants.optimal_flow.percentage}%)
                </span>
              </div>
              <div className="text-[11px] font-semibold text-emerald-800/80 mt-1">
                70%+ of the marks · within the exam&apos;s time
              </div>
              <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
                You scored well in the time the exam allows for these marks.
              </p>
            </button>

            {/* Speed Trap */}
            <button
              type="button"
              onClick={() => setSelectedVelocity(selectedVelocity === "speed_trap" ? null : "speed_trap")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedVelocity === "speed_trap"
                  ? "border-rose-500 bg-rose-50/90 shadow-sm scale-[1.01]"
                  : "border-rose-200/90 bg-[#FFF5F5] hover:border-rose-400 hover:bg-rose-50/60"
              }`}
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🚨</span>
                  <span className="font-fun font-bold text-rose-950 text-sm">
                    Rushed
                  </span>
                </div>
                <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300">
                  {v.quadrants.speed_trap.count} ({v.quadrants.speed_trap.percentage}%)
                </span>
              </div>
              <div className="text-[11px] font-semibold text-rose-800/80 mt-1">
                under 70% · under half the exam&apos;s time
              </div>
              <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
                Marks were lost quickly. Reading the question again before answering may help.
              </p>
            </button>

            {/* Hesitant Success */}
            <button
              type="button"
              onClick={() => setSelectedVelocity(selectedVelocity === "hesitant_success" ? null : "hesitant_success")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedVelocity === "hesitant_success"
                  ? "border-indigo-500 bg-indigo-50/90 shadow-sm scale-[1.01]"
                  : "border-indigo-200/80 bg-[#F8F9FF] hover:border-indigo-400 hover:bg-indigo-50/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🐢</span>
                  <span className="font-fun font-bold text-indigo-950 text-sm">
                    Right, but slow
                  </span>
                </div>
                <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-indigo-100 text-indigo-800 border border-indigo-300">
                  {v.quadrants.hesitant_success.count} ({v.quadrants.hesitant_success.percentage}%)
                </span>
              </div>
              <div className="text-[11px] font-semibold text-indigo-800/80 mt-1">
                70%+ of the marks · over the exam&apos;s time
              </div>
              <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
                You got the marks but took longer than the exam allows. Timed practice will help.
              </p>
            </button>

            {/* Time Sink */}
            <button
              type="button"
              onClick={() => setSelectedVelocity(selectedVelocity === "time_sink" ? null : "time_sink")}
              className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all cursor-pointer ${
                selectedVelocity === "time_sink"
                  ? "border-amber-500 bg-amber-50/90 shadow-sm scale-[1.01]"
                  : "border-slate-200/90 bg-[#FFFDF5] hover:border-amber-400 hover:bg-amber-50/50"
              }`}
            >
              <div className="flex items-center justify-between gap-2 w-full">
                <div className="flex items-center gap-2">
                  <span className="text-xl">⏳</span>
                  <span className="font-fun font-bold text-amber-950 text-sm">
                    Stuck
                  </span>
                </div>
                <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                  {v.quadrants.time_sink.count} ({v.quadrants.time_sink.percentage}%)
                </span>
              </div>
              <div className="text-[11px] font-semibold text-amber-800/80 mt-1">
                under 70% · took longer
              </div>
              <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">
                Time went in without the marks. In an exam, it can be better to move on and come back.
              </p>
            </button>
          </div>
        )}

        {/* Selected Quadrant Item Drill-Down */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
          <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
            <div className="font-fun font-bold text-xs uppercase tracking-wider text-slate-700">
              {mode === "epistemic" ? (
                <>
                  {selectedEpistemic === "dangerous_blindspot" && "⚠️ Blindspot Traps to Review"}
                  {selectedEpistemic === "true_mastery" && "🎯 Confident & Mastered Questions"}
                  {selectedEpistemic === "hesitant_mastery" && "🌟 Hesitant Victories (Trust Your Preparation!)"}
                  {selectedEpistemic === "known_gap" && "🔍 Honest Gaps to Practice"}
                </>
              ) : (
                <>
                  {selectedVelocity === "optimal_flow" && "Right, in time"}
                  {selectedVelocity === "speed_trap" && "Rushed: marks lost quickly"}
                  {selectedVelocity === "hesitant_success" && "Right, but over the exam's time"}
                  {selectedVelocity === "time_sink" && "Stuck: time without the marks"}
                </>
              )}
            </div>
            <span className="text-xs text-slate-400 font-medium">
              Showing {filteredItems.length} recent item{filteredItems.length === 1 ? "" : "s"}
            </span>
          </div>

          {filteredItems.length === 0 ? (
            <p className="text-xs text-slate-500 italic py-2">
              No questions currently in this diagnostic category.
            </p>
          ) : (
            <div className="space-y-2.5">
              {filteredItems.map((it: MetacognitionItem) => {
                const secPerMark =
                  it.time_spent_s && it.marks_available > 0
                    ? Math.round(it.time_spent_s / it.marks_available)
                    : null;

                return (
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
                        {secPerMark !== null && (
                          <>
                            <span className="text-slate-300">·</span>
                            <span
                              className={`font-fun font-bold px-1.5 py-0.5 rounded text-[11px] ${
                                it.velocity_category === "optimal_flow"
                                  ? "bg-emerald-100 text-emerald-800"
                                  : it.velocity_category === "speed_trap"
                                    ? "bg-rose-100 text-rose-800"
                                    : it.velocity_category === "time_sink"
                                      ? "bg-amber-100 text-amber-800"
                                      : "bg-indigo-100 text-indigo-800"
                              }`}
                            >
                              ⏱ {secPerMark}s per mark ({it.time_spent_s}s)
                            </span>
                          </>
                        )}
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
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-amber-100/90 text-amber-900 text-[11px] font-medium border border-slate-200"
                          >
                            <span>⚠️</span> {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
