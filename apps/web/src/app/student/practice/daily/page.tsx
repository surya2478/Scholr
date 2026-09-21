"use client";

import Link from "next/link";
import { useState } from "react";
import { EvaluationCard } from "@/components/EvaluationCard";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { DailyItem, DailyPractice, Evaluation } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

// Today's practice set (docs/STUDENT-APP.md step 4): a few short questions chosen from her plan, her mistakes,
// what is due for revision and what she has just studied. The set is fixed for the day; progress is real marks.
const STATUS: Record<DailyItem["status"], { label: string; tone: "neutral" | "good" | "warn" | "brand" }> = {
  to_do: { label: "To do", tone: "neutral" },
  answered: { label: "Answered", tone: "brand" },
  marked: { label: "Marked", tone: "good" },
  provisional: { label: "Waiting for a parent's check", tone: "warn" },
};

function Feedback({ evaluationId }: { evaluationId: string }) {
  const [open, setOpen] = useState(false);
  const evaluation = useApi<Evaluation>(open ? `/evaluations/${evaluationId}` : null);
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="self-start text-xs font-fun font-bold text-orange-600 hover:underline">
        See the feedback
      </button>
    );
  }
  return evaluation.data ? <EvaluationCard evaluation={evaluation.data} /> : null;
}

export default function DailyPracticePage() {
  const set = useApi<DailyPractice>("/practice/daily");
  const data = set.data;
  // Questions answered on this visit stay open, so the marking and feedback stay in view after the refresh.
  const [answeredHere, setAnsweredHere] = useState<Set<string>>(new Set());

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-fun font-bold text-slate-900">Today&apos;s practice set</h1>
          <p className="text-sm text-slate-600 font-medium">
            A few short questions picked for you today. Each one says why it&apos;s here.
          </p>
        </div>
        {data && data.total > 0 && (
          <Chip tone={data.done === data.total ? "good" : "brand"}>
            {data.done} of {data.total} done
          </Chip>
        )}
      </div>

      {set.error ? <ErrorNote error={set.error} /> : null}
      {set.loading && <p className="text-sm text-slate-500">Choosing today&apos;s questions…</p>}
      {data?.notice && <Empty>{data.notice}</Empty>}

      {data?.items.map((item, index) => (
        <Card key={item.item_id} tone={item.status === "marked" ? "emerald" : "default"}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex flex-col gap-0.5">
              <span className="text-xs font-semibold text-slate-500">
                {index + 1}. {item.subject_name} ·{" "}
                <Link href={`/student/learn/topic/${item.objective_id}`} className="text-orange-600 hover:underline">
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
          {item.evaluation_id && !answeredHere.has(item.item_id) && <Feedback evaluationId={item.evaluation_id} />}
          {(item.status === "to_do" || answeredHere.has(item.item_id)) && (
            <TryQuestion
              item={{ id: item.item_id, source_ref: item.source_ref, label: item.label, marks: item.marks, command_word: null }}
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
                void set.reload();
              }}
            />
          )}
        </Card>
      ))}
    </div>
  );
}
