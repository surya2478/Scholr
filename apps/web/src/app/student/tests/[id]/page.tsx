"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { AnswerBox } from "@/components/AnswerBox";
import { SittingClock } from "@/components/SittingClock";
import { Button, Card, Chip, ErrorNote } from "@/components/ui";
import { api, type Assessment, type Evaluation } from "@/lib/api";
import { KIND_LABELS } from "@/lib/format";
import { useApi } from "@/lib/useApi";

export default function TestDetail() {
  const { id } = useParams<{ id: string }>();
  const test = useApi<Assessment>(`/assessments/${id}`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [marking, setMarking] = useState<string | null>(null);

  async function act(path: "start" | "submit") {
    if (path === "submit" && !window.confirm("Submit the test? You cannot change answers afterwards.")) return;
    setBusy(true);
    setError(null);
    try {
      test.setData(await api<Assessment>(`/assessments/${id}/${path}`, { method: "POST" }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function markAll() {
    const unmarked = test.data?.items.filter((i) => i.attempt_id && !i.evaluation_status) ?? [];
    setError(null);
    for (const item of unmarked) {
      setMarking(`Marking question ${item.position + 1}…`);
      try {
        await api<Evaluation>(`/attempts/${item.attempt_id}/evaluate`, { method: "POST" });
      } catch (err) {
        setError(err);
        break;
      }
    }
    setMarking(null);
    await test.reload();
  }

  const a = test.data;
  if (test.error) return <ErrorNote error={test.error} />;
  if (!a) return <p className="text-sm text-muted">Loading…</p>;
  const inProgress = a.status === "in_progress";
  const submitted = a.status === "submitted" || a.status === "evaluated";

  return (
    <div className="space-y-6">
      {/* Test Header Banner */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <Link
              href="/student/tests"
              className="inline-flex items-center gap-1 text-xs font-fun font-bold text-orange-600 hover:text-orange-700 bg-white/80 border border-orange-200 px-3 py-1 rounded-xl mb-2"
            >
              ← Back to tests
            </Link>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              {KIND_LABELS[a.kind] ?? a.kind}
              {a.form_code ? ` · Form ${a.form_code}` : ""}
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium">
              {a.items.length} questions · {a.total_marks} marks total
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {a.kind === "exam_style" && inProgress && <SittingClock assessmentId={a.id} />}
            {a.no_help && (
              <span className="px-3 py-1 rounded-xl bg-amber-100 text-amber-900 text-xs font-bold border border-amber-300">
                🔒 Exam conditions (no hints or Tutor until you submit)
              </span>
            )}
            {a.status === "draft" && (
              <Button disabled={busy} onClick={() => act("start")}>
                Start test now →
              </Button>
            )}
            {inProgress && (
              <Button disabled={busy} onClick={() => act("submit")}>
                Submit finished test ✓
              </Button>
            )}
            {submitted && a.items.some((i) => i.attempt_id && !i.evaluation_status) && (
              <Button disabled={Boolean(marking)} onClick={markAll}>
                {marking ?? "Mark my answers 🪄"}
              </Button>
            )}
            {a.score && (
              <div className="bg-white border-2 border-emerald-200 px-4 py-2 rounded-2xl shadow-2xs">
                <span className="text-xs text-slate-500 font-medium block">Total Score:</span>
                <span className="text-lg font-fun font-bold text-emerald-700">
                  {a.score.awarded} / {a.score.available}
                </span>
                {!a.score.final && <span className="text-[10px] text-amber-700 block font-medium">(provisional)</span>}
              </div>
            )}
          </div>
        </div>
        {error ? <div className="mt-3"><ErrorNote error={error} /></div> : null}
      </div>

      {/* Question Cards */}
      <div className="space-y-4">
        {a.items.map((item) => (
          <Card
            key={item.position}
            title={`Question ${item.position + 1}`}
            subtitle={`${item.marks} marks`}
          >
            {!item.question ? (
              <div className="p-4 rounded-2xl bg-amber-50/60 border border-amber-200 text-xs text-slate-600 font-medium">
                Tap &ldquo;Start test&rdquo; above to reveal this question.
              </div>
            ) : item.attempt_id ? (
              <div className="flex flex-wrap items-center gap-3 p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-200 text-sm font-medium text-emerald-900">
                <Chip tone="good">Answered ✓</Chip>
                {item.marks_awarded !== null && (
                  <span className="font-fun font-bold">
                    {item.marks_awarded} / {item.marks} marks {item.evaluation_status === "needs_review" ? "(provisional review)" : ""}
                  </span>
                )}
              </div>
            ) : inProgress ? (
              <AnswerBox
                question={item.question}
                assessmentId={a.id}
                markNow={!a.no_help}
                onAnswered={() => void test.reload()}
              />
            ) : (
              <p className="text-sm text-slate-400 font-medium">Not answered.</p>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
