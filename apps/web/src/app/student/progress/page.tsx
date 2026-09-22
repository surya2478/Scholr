"use client";

import { CalibrationMatrix } from "@/components/CalibrationMatrix";
import { IndependenceMeter } from "@/components/IndependenceMeter";
import { SubjectLevels } from "@/components/SubjectLevels";
import { Card, Chip, Empty, ErrorNote, LevelBar, Stat } from "@/components/ui";
import type { Mastery, Metacognition, ProgressSummary } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function Progress() {
  const summary = useApi<ProgressSummary>("/progress/summary");
  const metacognition = useApi<Metacognition>("/progress/metacognition");
  const mastery = useApi<Mastery[]>("/mastery");
  const skills = useApi<{ subject_id: string; skill_code: string; skill_name: string; score: number; evidence_count: number }[]>(
    "/skills",
  );
  const week = summary.data?.week;

  return (
    <div className="space-y-6">
      {/* Friendly Header */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
              <span>🏆</span> Cambridge Mastery Dashboard
            </span>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              My Learning Progress & Skills
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium max-w-xl">
              Levels reflect marked work and verified answers, not just time spent in the app.
            </p>
          </div>
          <div className="h-16 w-16 rounded-3xl bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-3xl text-white shadow-md select-none animate-float">
            🌟
          </div>
        </div>
      </div>

      {/* This Week Stats */}
      <Card title="This Week's Activity" subtitle="Verified practice and completed missions">
        {summary.error ? <ErrorNote error={summary.error} /> : null}
        {week && (
          <div className="grid grid-cols-2 gap-3.5 md:grid-cols-4">
            <Stat label="Answers marked" value={String(week.attempts_evaluated)} icon="📝" />
            <Stat label="Active days" value={`${week.active_days} of 7`} icon="📅" hint="Consistency wins!" />
            <Stat label="Plan items done" value={`${week.plan_items_completed} of ${week.plan_items_total}`} icon="🎯" />
            <Stat label="Items skipped" value={String(week.plan_items_skipped)} icon="⏩" />
          </div>
        )}
      </Card>

      {/* Metacognitive Calibration Matrix (Confidence vs Performance) */}
      <CalibrationMatrix data={metacognition.data} />

      {/* Socratic Independence Index (Anti-Dependency) */}
      <IndependenceMeter data={metacognition.data?.independence} />

      {/* Topics by Level */}
      <Card title="Topics by Mastery Level" subtitle="Based on evaluated answers and SymPy proofs">
        <div className="space-y-3">
          {summary.data?.subjects.map((s) => (
            <SubjectLevels key={s.subject_id} subject={s} />
          ))}
        </div>
      </Card>

      {/* Exam Skills / Cambridge Assessment Objectives */}
      <Card
        title="Cambridge Exam Skills (AO Breakdown)"
        subtitle="How your marks split across official Assessment Objectives (from checked exam questions)"
      >
        {skills.data?.length === 0 && (
          <Empty>Skill scores appear once written answers have verified marks.</Empty>
        )}
        <ul className="flex flex-col gap-2.5">
          {skills.data?.map((sk) => (
            <li
              key={`${sk.subject_id}${sk.skill_code}`}
              className="flex flex-wrap items-center gap-3 p-3.5 rounded-2xl border border-amber-200/70 bg-[#FFFDF9] shadow-2xs"
            >
              <span className="px-2.5 py-1 rounded-xl bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200 flex-none">
                {sk.skill_code}
              </span>
              <span className="min-w-0 flex-1 text-sm font-semibold text-slate-800">
                {sk.skill_name}
              </span>
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="h-2.5 w-36 overflow-hidden rounded-full bg-slate-100 flex-none">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500"
                    style={{ width: `${Math.round(sk.score * 100)}%` }}
                  />
                </div>
                <span className="text-xs font-fun font-bold text-slate-700 min-w-[70px] text-right">
                  {Math.round(sk.score * 100)}% ({sk.evidence_count})
                </span>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {/* Topics with Evidence */}
      <Card title="Topics with Evidence" subtitle="Detailed mastery ranking by objective">
        {mastery.error ? <ErrorNote error={mastery.error} /> : null}
        {mastery.data?.length === 0 && (
          <Empty>Answer some practice questions in the Maths Lab or Sociology Club to start building your topic levels.</Empty>
        )}
        <ul className="flex flex-col divide-y divide-amber-100">
          {mastery.data
            ?.slice()
            .sort((a, b) => a.objective_code.localeCompare(b.objective_code, undefined, { numeric: true }))
            .map((m) => (
              <li key={m.objective_id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="w-14 text-xs font-fun font-bold text-orange-700 bg-orange-50 px-2 py-0.5 rounded-md border border-orange-200/80 text-center flex-none">
                  {m.objective_code}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">
                  {m.objective_statement}
                </span>
                {m.retention_risk === "high" && <Chip tone="warn">Review due ⏰</Chip>}
                <LevelBar level={m.level} />
                <span className="w-24 text-right text-xs font-fun font-bold text-slate-700 flex-none">
                  {m.level_name}
                </span>
              </li>
            ))}
        </ul>
      </Card>
    </div>
  );
}
