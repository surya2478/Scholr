"use client";

import { CalibrationMatrix } from "@/components/CalibrationMatrix";
import { ExamPicture } from "@/components/ExamPicture";
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
      {/* Header */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 md:p-8 text-white shadow-xl">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-2 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-emerald-300 font-mono text-xs font-bold border border-white/15">
              <span>📈</span> YOUR PROGRESS
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Performance Analytics &amp; Syllabus Mastery
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-xl leading-relaxed">
              Every mastery level, Brier calibration score, and Assessment Objective breakdown is computed from verified answers and marked scripts.
            </p>
          </div>
          <div className="h-16 w-16 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center font-mono text-xl font-extrabold text-emerald-300 flex-none">
            AO
          </div>
        </div>
      </div>

      {/* One honest exam picture per subject (improvement 10) */}
      <ExamPicture />

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
              className="flex flex-wrap items-center gap-3 p-3.5 rounded-2xl border border-slate-200/90 bg-white shadow-2xs"
            >
              <span className="px-2.5 py-1 rounded-xl bg-blue-50 text-blue-800 text-xs font-fun font-bold border border-blue-200 flex-none">
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
        <ul className="flex flex-col divide-y divide-slate-100">
          {mastery.data
            ?.slice()
            .sort((a, b) => a.objective_code.localeCompare(b.objective_code, undefined, { numeric: true }))
            .map((m) => (
              <li key={m.objective_id} className="flex flex-wrap items-center gap-3 py-3">
                <span className="w-14 text-xs font-fun font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded-md border border-blue-200/80 text-center flex-none">
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
