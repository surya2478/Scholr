"use client";

import { useEffect, useMemo, useState } from "react";
import { ChapterTopicSelector } from "@/components/curriculum/ChapterTopicSelector";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import {
  api,
  type AssessmentBrief,
  type ExamCategory,
  type ExamFromTopicsIn,
  type SubjectTree,
} from "@/lib/api";
import { shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

type ExamTierInfo = {
  category: ExamCategory;
  title: string;
  badge: string;
  emoji: string;
  defaultMins: number;
  defaultMarks: number;
  description: string;
};

const EXAM_TIERS: ExamTierInfo[] = [
  {
    category: "practice_exam",
    title: "Practice Exam",
    badge: "Chapter Test",
    emoji: "📝",
    defaultMins: 35,
    defaultMarks: 30,
    description: "A short test on one to three chapters.",
  },
  {
    category: "pre_term",
    title: "Pre-Term Exam",
    badge: "Diagnostic",
    emoji: "📅",
    defaultMins: 50,
    defaultMarks: 45,
    description: "A test across several chapters, to see what has stayed with you before school exams.",
  },
  {
    category: "term",
    title: "Term Exam",
    badge: "Term Paper",
    emoji: "📋",
    defaultMins: 75,
    defaultMarks: 60,
    description: "A longer test on the term's chapters, built from past-paper and practice questions.",
  },
  {
    category: "mid_term",
    title: "Mid-Term Exam",
    badge: "Half-Year Mock",
    emoji: "⏳",
    defaultMins: 90,
    defaultMarks: 75,
    description: "A test on the first half of the year's chapters, with a clock.",
  },
  {
    category: "final",
    title: "Final Exam",
    badge: "Whole syllabus",
    emoji: "🏆",
    defaultMins: 120,
    defaultMarks: 100,
    description: "A long test on every chapter you choose. It is not a real Cambridge paper — for that, sit a timed past paper.",
  },
];

const TIER_LABELS: Record<string, string> = {
  practice_exam: "Practice Exam",
  pre_term: "Pre-Term Exam",
  term: "Term Exam",
  mid_term: "Mid-Term Exam",
  final: "Final Exam",
};

export default function ParentExaminationsPage() {
  const { id: studentId, query, subjects: enrolled } = useLinkedStudent();
  // Only subjects Scholr teaches have questions to set.
  const subjects = enrolled.filter((e) => e.stage === "taught");
  const subjectNames = useMemo(
    () => Object.fromEntries(subjects.map((s) => [s.subject_id, s.subject_name])),
    [subjects]
  );

  const assessments = useApi<AssessmentBrief[]>(studentId ? `/assessments?${query}` : null);

  // Exam Builder State
  const [selectedTier, setSelectedTier] = useState<ExamCategory>("term");
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [selectedObjectiveIds, setSelectedObjectiveIds] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState<string>("");
  const [durationMins, setDurationMins] = useState<number>(75);
  const [targetMarks, setTargetMarks] = useState<number>(60);
  const [scheduling, setScheduling] = useState(false);
  const [successNote, setSuccessNote] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  // Auto-select first subject
  useEffect(() => {
    if (subjects.length > 0 && !selectedSubjectId) {
      setSelectedSubjectId(subjects[0].subject_id);
    }
  }, [subjects, selectedSubjectId]);

  const tierConfig = useMemo(() => EXAM_TIERS.find((t) => t.category === selectedTier)!, [selectedTier]);

  useEffect(() => {
    setDurationMins(tierConfig.defaultMins);
    setTargetMarks(tierConfig.defaultMarks);
  }, [tierConfig]);

  // Load subject tree
  const tree = useApi<SubjectTree>(selectedSubjectId ? `/subjects/${selectedSubjectId}/tree` : null);

  async function handleScheduleExam() {
    if (!studentId || !selectedSubjectId || selectedObjectiveIds.size === 0) return;
    setScheduling(true);
    setError(null);
    setSuccessNote(null);
    try {
      const finalTitle =
        title.trim() ||
        `${tierConfig.title}: ${subjectNames[selectedSubjectId] ?? "Subject"} (${selectedObjectiveIds.size} Objectives)`;

      const payload: ExamFromTopicsIn = {
        subject_id: selectedSubjectId,
        title: finalTitle,
        exam_category: selectedTier,
        objective_ids: Array.from(selectedObjectiveIds),
        target_marks: targetMarks,
        duration_minutes: durationMins,
      };

      await api(`/assessments/from-topics?${query}`, {
        method: "POST",
        json: payload,
      });

      setSuccessNote(`Successfully scheduled ${finalTitle}! Paper is ready for the student in their Examinations hub.`);
      setTitle("");
      setSelectedObjectiveIds(new Set());
      await assessments.reload();
    } catch (err) {
      setError(err);
    } finally {
      setScheduling(false);
    }
  }

  const examList = useMemo(() => {
    return (assessments.data ?? []).filter(
      (a) => a.kind === "topic_exam"
    );
  }, [assessments.data]);

  return (
    <div className="flex flex-col gap-6">
      {/* Friendly Banner */}
      <section className="relative overflow-hidden rounded-3xl border border-indigo-100 bg-gradient-to-r from-[#F5F6FF] via-[#FAF5FF] to-[#FFF9F2] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-indigo-800 shadow-xs">
              <span>🏛️</span> Formal Examination Management
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              Examinations &amp; Term Papers
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Set a timed test on chosen chapters, from past-paper and practice questions. It is sat without hints or the Tutor, and marked after it is submitted.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-indigo-200/60 bg-white/90 p-4 shadow-xs">
            <div className="text-3xl">📝</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Exam Hall Simulation</div>
              <div className="font-fun text-sm font-bold text-ink">Strict Exam Rules</div>
              <div className="text-[11px] text-muted">Timed · Mark Scheme Evaluated</div>
            </div>
          </div>
        </div>
      </section>

      {error ? <ErrorNote error={error} /> : null}
      {successNote && (
        <div className="rounded-2xl border border-emerald-300 bg-emerald-50/90 p-4 text-xs font-fun font-bold text-emerald-800 shadow-xs">
          ✅ {successNote}
        </div>
      )}

      {/* 5 Exam Tiers */}
      <div>
        <h2 className="text-sm font-fun font-bold text-slate-800 mb-2.5">
          1. Select Examination Tier to Schedule
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {EXAM_TIERS.map((tier) => {
            const isSelected = selectedTier === tier.category;
            return (
              <button
                key={tier.category}
                type="button"
                onClick={() => setSelectedTier(tier.category)}
                className={`flex flex-col text-left p-4 rounded-2xl border-2 transition-all shadow-2xs ${
                  isSelected
                    ? "border-indigo-600 bg-white ring-2 ring-indigo-500/20 scale-102"
                    : "border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50/50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-2xl">{tier.emoji}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      isSelected
                        ? "bg-indigo-100 text-indigo-700"
                        : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {tier.badge}
                  </span>
                </div>
                <div className="mt-2 font-fun font-bold text-slate-900 text-sm">
                  {tier.title}
                </div>
                <div className="mt-1 text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                  {tier.description}
                </div>
                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px] font-medium text-slate-600">
                  <span>⏱ {tier.defaultMins} min</span>
                  <span>🎯 {tier.defaultMarks} marks</span>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Scope Builder */}
      <Card
        title={`2. Configure & Schedule ${tierConfig.title}`}
        subtitle="Choose which chapters the student will be tested on, paper marks, and duration limit."
      >
        {/* Subject Selection */}
        <div className="space-y-3 pb-4 border-b border-line-soft">
          <label className="text-xs font-bold text-slate-700 block">
            Select Subject:
          </label>
          <div className="flex flex-wrap gap-2">
            {subjects.map((sub) => {
              const isSelected = sub.subject_id === selectedSubjectId;
              return (
                <button
                  key={sub.subject_id}
                  type="button"
                  onClick={() => {
                    setSelectedSubjectId(sub.subject_id);
                    setSelectedObjectiveIds(new Set());
                  }}
                  className={`flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-fun font-bold transition ${
                    isSelected
                      ? "bg-indigo-600 text-white shadow-xs"
                      : "bg-slate-100 text-slate-700 hover:bg-slate-200/80"
                  }`}
                >
                  <span>{sub.subject_name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Hierarchical Chapter -> Numbers -> Topics Checklist */}
        <div className="space-y-2 py-3 border-b border-line-soft">
          <label className="text-xs font-bold text-slate-700 block">
            Select Chapters &amp; Topics for Examination Scope:
          </label>

          {tree.error && <ErrorNote error={tree.error} />}

          <ChapterTopicSelector
            tree={tree.data}
            loading={tree.loading}
            selectedObjectiveIds={selectedObjectiveIds}
            onChangeSelectedObjectives={setSelectedObjectiveIds}
            accentColor="indigo"
          />
        </div>

        {/* Parameters & Schedule Button */}
        <div className="pt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
          <div>
            <label className="text-xs font-bold text-slate-700 block mb-1">
              Custom Exam Title:
            </label>
            <input
              type="text"
              placeholder={`${tierConfig.title}: ${subjectNames[selectedSubjectId] ?? "Subject"}`}
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-10 w-full rounded-xl border border-line bg-white px-3 text-xs font-medium text-slate-900 focus:border-indigo-600 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">
                Target Marks:
              </label>
              <input
                type="number"
                min={10}
                max={120}
                value={targetMarks}
                onChange={(e) => setTargetMarks(Number(e.target.value))}
                className="h-10 w-full rounded-xl border border-line bg-white px-3 text-xs font-medium text-slate-900 focus:border-indigo-600 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-bold text-slate-700 block mb-1">
                Duration (min):
              </label>
              <input
                type="number"
                min={15}
                max={180}
                value={durationMins}
                onChange={(e) => setDurationMins(Number(e.target.value))}
                className="h-10 w-full rounded-xl border border-line bg-white px-3 text-xs font-medium text-slate-900 focus:border-indigo-600 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <Button
              disabled={selectedObjectiveIds.size === 0 || scheduling}
              onClick={handleScheduleExam}
              className="w-full h-10 justify-center bg-indigo-600 hover:bg-indigo-700"
            >
              {scheduling ? "Scheduling Examination…" : `Schedule Exam (${selectedObjectiveIds.size} topics) →`}
            </Button>
          </div>
        </div>
      </Card>

      {/* Student's Scheduled & Past Examinations */}
      <Card
        title="Student's Examination Papers"
        subtitle="All scheduled and completed examinations for your linked student."
      >
        {assessments.loading && <p className="text-xs text-slate-500">Loading student exam records…</p>}
        {examList.length === 0 && (
          <Empty>No examinations set for the student yet. Schedule an examination above!</Empty>
        )}

        <div className="flex flex-col gap-2.5 pt-1">
          {examList.map((exam) => {
            const categoryKey = (exam.config?.exam_category || exam.form_code || "practice_exam") as string;
            const tierTitle = TIER_LABELS[categoryKey] ?? "Exam Paper";
            const isCompleted = exam.status === "evaluated" || exam.status === "submitted";
            const customTitle = exam.config?.title || `${subjectNames[exam.subject_id] ?? "Subject"} · ${tierTitle}`;

            return (
              <div
                key={exam.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line-soft bg-white p-4 shadow-2xs hover:border-indigo-300 transition"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-700 text-lg">
                    📋
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-fun font-bold text-slate-900">
                        {customTitle}
                      </span>
                      <Chip tone="neutral">{tierTitle}</Chip>
                    </div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {subjectNames[exam.subject_id] ?? "Subject"} · {exam.total_marks} marks total · scheduled {shortDate(exam.created_at)}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <Chip tone={isCompleted ? "good" : exam.status === "in_progress" ? "brand" : "neutral"}>
                    {exam.status === "in_progress"
                      ? "In progress"
                      : isCompleted
                      ? "Completed"
                      : "Not started"}
                  </Chip>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
