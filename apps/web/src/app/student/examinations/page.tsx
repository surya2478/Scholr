"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useMe } from "@/components/AppShell";
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

export default function StudentExaminationsPage() {
  const router = useRouter();
  const me = useMe();
  // Only subjects Scholr teaches have questions to set.
  const enrollments = (me?.student?.enrollments ?? []).filter((e) => e.stage === "taught");

  // Assessments list
  const assessments = useApi<AssessmentBrief[]>("/assessments");

  // Exam Builder State
  const [selectedTier, setSelectedTier] = useState<ExamCategory>("term");
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [selectedObjectiveIds, setSelectedObjectiveIds] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState<string>("");
  const [durationMins, setDurationMins] = useState<number>(75);
  const [targetMarks, setTargetMarks] = useState<number>(60);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Auto-select first subject
  useEffect(() => {
    if (enrollments.length > 0 && !selectedSubjectId) {
      setSelectedSubjectId(enrollments[0].subject_id);
    }
  }, [enrollments, selectedSubjectId]);

  // Update defaults when tier changes
  const tierConfig = useMemo(() => EXAM_TIERS.find((t) => t.category === selectedTier)!, [selectedTier]);

  useEffect(() => {
    setDurationMins(tierConfig.defaultMins);
    setTargetMarks(tierConfig.defaultMarks);
  }, [tierConfig]);

  // Load subject tree
  const tree = useApi<SubjectTree>(selectedSubjectId ? `/subjects/${selectedSubjectId}/tree` : null);

  // Map subject names
  const subjectNames = useMemo(
    () => Object.fromEntries(enrollments.map((e) => [e.subject_id, e.subject_name])),
    [enrollments]
  );

  // Create Exam
  async function handleCreateExam() {
    if (!selectedSubjectId || selectedObjectiveIds.size === 0) return;
    setCreating(true);
    setError(null);
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

      const result = await api<{ id: string }>("/assessments/from-topics", {
        method: "POST",
        json: payload,
      });

      // Route directly to exam sitting hall
      router.push(`/student/tests/${result.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setCreating(false);
    }
  }

  // Filter exam-style assessments
  const examList = useMemo(() => {
    return (assessments.data ?? []).filter(
      (a) => a.kind === "topic_exam"
    );
  }, [assessments.data]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0B1528] via-[#122240] to-[#1E3A8A] p-6 md:p-7 text-white shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/20 text-blue-200 text-[11px] font-bold uppercase tracking-wider border border-blue-400/30">
              <span>🏛️</span> Custom Mock Paper Builder · Timed Simulation
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              Mock Examinations Hub
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-2xl leading-relaxed">
              Simulate formal examination conditions across Practice, Pre-Term, Term, Mid-Term, and Final Exams.
              Select any chapters or topics across the syllabus to assemble a timed, verified paper with full Cambridge marking rubrics.
            </p>
          </div>
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 shrink-0">
            <div className="flex items-center gap-2.5 rounded-xl border border-white/15 bg-white/10 backdrop-blur-xs px-4 py-2.5">
              <div className="text-xl">⏱️</div>
              <div>
                <div className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">Exam Rules</div>
                <div className="text-xs font-extrabold text-amber-300">Strict Timer · No AI Hints</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {error ? <ErrorNote error={error} /> : null}

      {/* 5 Exam Tiers Grid */}
      <div>
        <h2 className="text-sm font-fun font-bold text-slate-800 mb-2.5">
          1. Select Examination Tier
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

      {/* Exam Scope & Chapter Builder */}
      <Card
        title={`2. Configure ${tierConfig.title} Paper`}
        subtitle="Select the subject and choose which chapters or topics will be tested on this paper."
      >
        {/* Subject Selection */}
        <div className="space-y-3 pb-4 border-b border-line-soft">
          <label className="text-xs font-bold text-slate-700 block">
            Select Subject:
          </label>
          <div className="flex flex-wrap gap-2">
            {enrollments.map((sub) => {
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

        {/* Paper Parameters & Assemble Button */}
        <div className="pt-4 grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
          <div>
            <label className="text-xs font-bold text-slate-700 block mb-1">
              Custom Exam Title (Optional):
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
              disabled={selectedObjectiveIds.size === 0 || creating}
              onClick={handleCreateExam}
              className="w-full h-10 justify-center bg-indigo-600 hover:bg-indigo-700"
            >
              {creating ? "Assembling Exam Paper…" : `Assemble Exam (${selectedObjectiveIds.size} topics) →`}
            </Button>
          </div>
        </div>
      </Card>

      {/* Previous & Scheduled Examinations */}
      <Card
        title="Recent & Scheduled Examinations"
        subtitle="Your topic exams: open one to sit it, carry on, or see how it was marked."
      >
        {assessments.loading && <p className="text-xs text-slate-500">Loading your exam records…</p>}
        {examList.length === 0 && (
          <Empty>No examinations generated yet. Assemble your first paper above to benchmark readiness!</Empty>
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
                      {subjectNames[exam.subject_id] ?? "Subject"} · {exam.total_marks} marks total · created {shortDate(exam.created_at)}
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
                  <Link
                    href={`/student/tests/${exam.id}`}
                    className="rounded-xl border border-indigo-200 bg-indigo-50/80 px-3 py-1.5 text-xs font-fun font-bold text-indigo-700 hover:bg-indigo-100 transition"
                  >
                    {isCompleted ? "Review Marks →" : "Sit Exam →"}
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
