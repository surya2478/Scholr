"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ChapterTopicSelector } from "@/components/curriculum/ChapterTopicSelector";
import { EvaluationCard } from "@/components/EvaluationCard";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import {
  api,
  type DailyItem,
  type DailyPractice,
  type Evaluation,
  type Question,
  type Stream,
  type SubjectTree,
} from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

const STATUS: Record<DailyItem["status"], { label: string; tone: "neutral" | "good" | "warn" | "brand" }> = {
  to_do: { label: "To do", tone: "neutral" },
  answered: { label: "Answered", tone: "brand" },
  marked: { label: "Marked", tone: "good" },
  provisional: { label: "Waiting for a parent's check", tone: "warn" },
};

function Feedback({ evaluationId, subjectId }: { evaluationId: string; subjectId: string }) {
  const [open, setOpen] = useState(false);
  const evaluation = useApi<Evaluation>(open ? `/evaluations/${evaluationId}` : null);
  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="self-start text-xs font-fun font-bold text-blue-600 hover:underline"
      >
        See the feedback
      </button>
    );
  }
  return evaluation.data ? <EvaluationCard evaluation={evaluation.data} subjectId={subjectId} /> : null;
}

// Shown when every question in today's set has been answered: the day has an end, and it says what tomorrow
// starts with. No points, no streak, no badge — the finish itself is the point (PRINCIPLES §UX).
function TodaysFinish({ data }: { data: DailyPractice }) {
  const waiting = data.items.filter((i) => i.status === "provisional").length;
  return (
    <section className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5 space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-fun font-bold text-emerald-950">That&apos;s today&apos;s set done.</h2>
        <span className="font-mono text-xs font-bold text-emerald-800">
          {data.total} question{data.total === 1 ? "" : "s"}
          {data.answering_minutes > 0 ? ` · ${data.answering_minutes} min answering` : ""}
        </span>
      </div>

      {waiting > 0 && (
        <p className="text-xs font-medium text-emerald-900">
          {waiting} of them {waiting === 1 ? "is" : "are"} waiting for a parent&apos;s check, so {waiting === 1 ? "its" : "their"} mark
          is not final yet.
        </p>
      )}

      {data.tomorrow.length > 0 ? (
        <div className="space-y-2">
          <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-800">Tomorrow starts with</h3>
          <ul className="flex flex-col gap-2">
            {data.tomorrow.map((t) => (
              <li
                key={t.objective_id}
                className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border border-emerald-200/80 bg-white/80 p-3"
              >
                <Link
                  href={`/student/learn/topic/${t.objective_id}`}
                  className="text-xs font-bold text-slate-900 hover:text-blue-600"
                >
                  {t.subject_name} · {t.objective_code} {t.objective_statement}
                </Link>
                {t.reason ? <span className="text-[11px] font-medium text-slate-500">{t.reason}</span> : null}
              </li>
            ))}
          </ul>
          <p className="text-[11px] text-emerald-900/80">
            Tomorrow&apos;s set is chosen in the morning, so this can change — anything you do between now and then
            changes what is waiting.
          </p>
        </div>
      ) : (
        <p className="text-xs font-medium text-emerald-900">
          Nothing is waiting for tomorrow yet: no open mistakes and nothing due for revision. Tomorrow&apos;s set will
          come from your plan.
        </p>
      )}

      <p className="text-xs text-slate-600">
        You are done for today. If you want more anyway, the{" "}
        <Link href="/student/practice" className="font-bold text-blue-600 hover:underline">
          question bank
        </Link>{" "}
        is always open.
      </p>
    </section>
  );
}

export default function TodaysHomeworkPage() {
  const streams = useApi<Stream[]>("/learn/streams");
  const daily = useApi<DailyPractice>("/practice/daily");
  const dailyData = daily.data;

  // Topic practice is for the subjects Scholr teaches: only they have questions and marking. IIT Foundation is
  // learnt in its own classes — Scholr records that time (below), it never sets IIT work.
  const practiceSubjects = Array.from(
    new Map(
      (streams.data ?? []).flatMap((s) => s.subjects).filter((s) => s.stage === "taught").map((s) => [s.id, s]),
    ).values(),
  );
  const [selectedSubjectId, setSelectedSubjectId] = useState<string>("");
  const [selectedObjectiveIds, setSelectedObjectiveIds] = useState<Set<string>>(new Set());
  const tree = useApi<SubjectTree>(selectedSubjectId ? `/subjects/${selectedSubjectId}/tree` : null);

  // "scheduled": today's set from the plan; "custom_topics": questions on topics she chose
  const [viewMode, setViewMode] = useState<"custom_topics" | "scheduled">("scheduled");
  const [customQuestions, setCustomQuestions] = useState<Question[]>([]);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [customError, setCustomError] = useState<unknown>(null);
  const [answeredHere, setAnsweredHere] = useState<Set<string>>(new Set());

  const firstSubject = practiceSubjects[0]?.id;
  useEffect(() => {
    if (!selectedSubjectId && firstSubject) setSelectedSubjectId(firstSubject);
  }, [firstSubject, selectedSubjectId]);

  // Fetch homework questions for selected topics
  async function loadQuestionsForTopics() {
    if (selectedObjectiveIds.size === 0) return;
    setLoadingQuestions(true);
    setCustomError(null);
    try {
      const questions = await api<Question[]>("/practice/questions/by-objectives", {
        method: "POST",
        json: {
          subject_id: selectedSubjectId,
          objective_ids: Array.from(selectedObjectiveIds),
          limit: 12,
        },
      });
      setCustomQuestions(questions);
      setViewMode("custom_topics");
      setTimeout(() => {
        document.getElementById("homework-questions-workspace")?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (err) {
      setCustomError(err);
    } finally {
      setLoadingQuestions(false);
    }
  }

  // Minutes come from her records (the planner's daily output): time answering, as the answer box measured it,
  // against the time today's plan has room for; and the IIT class and homework time she recorded for today.
  const answering = dailyData?.answering_minutes ?? 0;
  const planned = dailyData?.planned_minutes ?? null;
  const external = dailyData?.external_minutes ?? 0;
  const answeringPercent = planned ? Math.min(100, Math.round((answering / planned) * 100)) : 0;

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-[#0B1528] via-[#122240] to-[#1E3A8A] p-6 md:p-7 text-white shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/20 text-blue-200 text-[11px] font-bold uppercase tracking-wider border border-blue-400/30">
              <span>⚡</span> Daily Execution · Spaced Retrieval &amp; Topic Drills
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
              Daily Action Set &amp; Topic Drill Builder
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-2xl leading-relaxed">
              Complete today&apos;s scheduled question set from your study plan, or build a custom 12-question drill across any syllabus objectives.
            </p>
          </div>
          <Link
            href="/student/practice"
            className="self-start md:self-center inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 hover:bg-white/15 px-3.5 py-2 text-xs font-bold text-white transition"
          >
            🎯 Open Question Bank &amp; Past-Paper Lab →
          </Link>
        </div>

        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-3 pt-4 border-t border-white/15">
          <div className="rounded-xl border border-white/15 bg-white/10 backdrop-blur-xs p-3.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold text-white">Active Question Practice Today</span>
              <span className="rounded-full bg-blue-500/30 border border-blue-300/30 px-2.5 py-0.5 text-[11px] font-mono font-bold text-blue-100">
                {answering} min{planned ? ` / ${planned} min` : ""}
              </span>
            </div>
            {planned ? (
              <div className="mt-2.5 h-2 w-full rounded-full bg-white/15 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-400 to-blue-400 transition-all duration-500"
                  style={{ width: `${answeringPercent}%` }}
                />
              </div>
            ) : null}
            <p className="mt-1.5 text-[11px] text-slate-300">
              {planned
                ? "Timed automatically while you work on each question against today's target."
                : "Timed automatically while you work on each question."}
            </p>
          </div>

          <div className="rounded-xl border border-white/15 bg-white/10 backdrop-blur-xs p-3.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold text-white">IIT Foundation Classes Today</span>
              <span className="rounded-full bg-white/15 border border-white/20 px-2.5 py-0.5 text-[11px] font-mono font-bold text-slate-200">
                {external} min logged
              </span>
            </div>
            <p className="mt-1.5 text-[11px] text-slate-300">
              Completed in your external IIT Foundation batch.{" "}
              <Link href="/student/iit" className="font-bold text-amber-300 hover:underline">
                Log a class or problem set →
              </Link>
            </p>
          </div>
        </div>
      </div>

      {/* Subject & Syllabus/Topic Selector Card */}
      <Card
        title="Practise chosen topics"
        subtitle="Choose a subject and a chapter, then tick the topics you want questions on."
      >
        {/* Subjects Row */}
        <div className="flex flex-wrap gap-2 pb-3 border-b border-line-soft">
          {practiceSubjects.map((sub) => {
            const active = sub.id === selectedSubjectId;
            return (
              <button
                key={sub.id}
                type="button"
                onClick={() => {
                  setSelectedSubjectId(sub.id);
                  setSelectedObjectiveIds(new Set());
                }}
                className={`flex items-center gap-2 rounded-xl px-3.5 py-1.5 text-xs font-fun font-bold transition ${
                  active
                    ? "bg-slate-900 text-white shadow-xs"
                    : "bg-slate-100 text-slate-700 hover:bg-slate-200/80"
                }`}
              >
                <span>{sub.name}</span>
                {sub.syllabus_code && (
                  <span className="text-[10px] opacity-70 font-mono">({sub.syllabus_code})</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Hierarchical Chapter -> Numbers -> Topics Selector */}
        {tree.error && <ErrorNote error={tree.error} />}

        <div className="pt-2">
          <ChapterTopicSelector
            tree={tree.data}
            loading={tree.loading}
            selectedObjectiveIds={selectedObjectiveIds}
            onChangeSelectedObjectives={setSelectedObjectiveIds}
            accentColor="orange"
          />
        </div>

        {/* Action Button */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-line-soft">
          <span className="text-xs text-slate-500 font-medium">
            {selectedObjectiveIds.size > 0
              ? `Ready to generate practice set across ${selectedObjectiveIds.size} learning objectives.`
              : "Check mark any chapters and topics above to generate homework questions."}
          </span>
          <Button
            disabled={selectedObjectiveIds.size === 0 || loadingQuestions}
            onClick={loadQuestionsForTopics}
          >
            {loadingQuestions
              ? "Loading Questions…"
              : `Load Homework Questions (${selectedObjectiveIds.size} topics) →`}
          </Button>
        </div>
      </Card>

      {/* Homework Question Sets Workspace */}
      <div id="homework-questions-workspace" className="space-y-4 pt-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setViewMode("scheduled")}
              className={`rounded-xl px-3 py-1.5 text-xs font-fun font-bold transition ${
                viewMode === "scheduled"
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
              }`}
            >
              📅 Scheduled Daily Set ({dailyData?.total ?? 0})
            </button>
            {customQuestions.length > 0 && (
              <button
                type="button"
                onClick={() => setViewMode("custom_topics")}
                className={`rounded-xl px-3 py-1.5 text-xs font-fun font-bold transition ${
                  viewMode === "custom_topics"
                    ? "bg-orange-600 text-white"
                    : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50"
                }`}
              >
                📝 Selected Topics Homework ({customQuestions.length})
              </button>
            )}
          </div>

          {dailyData && dailyData.total > 0 && viewMode === "scheduled" && (
            <Chip tone={dailyData.done === dailyData.total ? "good" : "brand"}>
              {dailyData.done} of {dailyData.total} done
            </Chip>
          )}
        </div>

        {customError ? (
          <div className="space-y-2">
            <ErrorNote error={customError} />
            <Button variant="secondary" onClick={loadQuestionsForTopics}>
              ↻ Retry Loading Questions
            </Button>
          </div>
        ) : null}

        {/* View Mode: Custom Topics Homework */}
        {viewMode === "custom_topics" && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-blue-200 bg-blue-50/40 p-3 text-xs text-blue-900 font-medium">
              Questions on the topics you chose, ones you have not tried first. Each answer is marked as usual.
            </div>
            {customQuestions.length === 0 && (
              <Empty>No questions found for the selected topics. Try selecting additional chapters.</Empty>
            )}
            {customQuestions.map((q, idx) => (
              <Card key={q.id}>
                <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
                  <span className="text-xs font-bold text-slate-700">
                    Question {idx + 1} · {q.source_ref || "Homework Exercise"}
                  </span>
                  <Chip tone="neutral">{q.marks} marks</Chip>
                </div>
                <TryQuestion
                  item={{
                    id: q.id,
                    source_ref: q.source_ref,
                    label: q.source_ref || `Question ${idx + 1}`,
                    marks: q.marks,
                    command_word: q.command_word,
                    stem: q.stem,
                    context: q.context,
                  }}
                  askHref={(question) =>
                    tutorHref({
                      subjectId: q.subject_id,
                      about: q.stem,
                      ask: question,
                    })
                  }
                  onAnswered={() => {
                    setAnsweredHere((prev) => new Set(prev).add(q.id));
                    void daily.reload(); // her minutes today, from the timed answer
                  }}
                />
              </Card>
            ))}
          </div>
        )}

        {/* View Mode: Scheduled Daily Practice Set */}
        {viewMode === "scheduled" && (
          <div className="space-y-4">
            {daily.error ? <ErrorNote error={daily.error} /> : null}
            {daily.loading && <p className="text-sm text-slate-500">Choosing today&apos;s questions…</p>}
            {dailyData?.notice && <Empty>{dailyData.notice}</Empty>}
            {dailyData && dailyData.total > 0 && dailyData.done === dailyData.total && (
              <TodaysFinish data={dailyData} />
            )}

            {dailyData?.items.map((item, index) => (
              <Card key={item.item_id} tone={item.status === "marked" ? "emerald" : "default"}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-xs font-semibold text-slate-500">
                      {index + 1}. {item.subject_name} ·{" "}
                      <Link href={`/student/learn/topic/${item.objective_id}`} className="text-blue-600 hover:underline">
                        {item.objective_code} {item.objective_statement}
                      </Link>
                    </span>
                    <span className="text-sm font-medium text-slate-700">{item.reason}</span>
                  </div>
                  <Chip tone={STATUS[item.status].tone}>
                    {STATUS[item.status].label}
                    {item.marks_awarded !== null ? ` · ${item.marks_awarded}/${item.marks}` : ""}
                  </Chip>
                </div>
                {item.evaluation_id && !answeredHere.has(item.item_id) && <Feedback evaluationId={item.evaluation_id} subjectId={item.subject_id} />}
                {(item.status === "to_do" || answeredHere.has(item.item_id)) && (
                  <TryQuestion
                    item={{
                      id: item.item_id,
                      source_ref: item.source_ref,
                      label: item.label,
                      marks: item.marks,
                      command_word: null,
                    }}
                    askHref={(q) =>
                      tutorHref({
                        subjectId: item.subject_id,
                        objectiveId: item.objective_id,
                        about: item.objective_statement,
                        ask: q,
                      })
                    }
                    onAnswered={() => {
                      setAnsweredHere((prev) => new Set(prev).add(item.item_id));
                      void daily.reload();
                    }}
                  />
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
