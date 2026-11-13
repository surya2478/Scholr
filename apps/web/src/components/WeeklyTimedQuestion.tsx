"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, type TimedQuestion } from "@/lib/api";
import { Button, Card, Chip, ErrorNote } from "./ui";

// This week's timed question (improvement 4): one real long answer a week, against her papers' own clock.
// Everything shown comes from the server — the question, its minutes, and whether she has done it this week.
export function WeeklyTimedQuestion({ questions }: { questions: TimedQuestion[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  if (questions.length === 0) return null;

  async function start(q: TimedQuestion) {
    if (q.assessment_id) {
      router.push(`/student/tests/${q.assessment_id}`);
      return;
    }
    if (!window.confirm(`The clock starts now: ${q.item.minutes} minutes, no hints or Tutor until you submit. Ready?`)) {
      return;
    }
    setBusy(q.subject_id);
    setError(null);
    try {
      const started = await api<TimedQuestion>(`/subjects/${q.subject_id}/timed-question`, { method: "POST" });
      router.push(`/student/tests/${started.assessment_id}`);
    } catch (err) {
      setError(err);
      setBusy(null);
    }
  }

  return (
    <Card
      title="This week's timed question"
      subtitle="One real exam answer a week, written against the clock. Writing to time is a skill of its own."
    >
      {error ? <ErrorNote error={error} /> : null}
      <ul className="flex flex-col gap-3">
        {questions.map((q) => (
          <li key={q.subject_id} className="rounded-xl border border-line-soft bg-tile p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <div className="text-xs font-bold uppercase tracking-wide text-muted">{q.subject_name}</div>
                <div className="text-sm font-semibold text-ink">
                  {q.item.marks}-mark {q.item.command_word ? `"${q.item.command_word}" ` : ""}question
                  {q.item.objective_code ? ` · ${q.item.objective_code} ${q.item.objective_statement ?? ""}` : ""}
                </div>
                <div className="text-xs text-muted">
                  {q.item.label} · <b className="text-ink-2">{q.item.minutes} minutes</b>, your exam&apos;s own pace
                </div>
              </div>
              <div className="flex flex-none items-center gap-2">
                {q.status === "to_do" && (
                  <Button disabled={busy === q.subject_id} onClick={() => start(q)}>
                    Start the clock
                  </Button>
                )}
                {q.status === "in_progress" && (
                  <Button onClick={() => start(q)}>Carry on</Button>
                )}
                {(q.status === "submitted" || q.status === "marked") && (
                  <>
                    <Chip tone={q.over_time ? "warn" : "good"}>
                      {q.minutes_used !== null ? `Done in ${q.minutes_used} of ${q.item.minutes} min` : "Done"}
                    </Chip>
                    <Button onClick={() => start(q)}>{q.status === "submitted" ? "Get it marked" : "See feedback"}</Button>
                  </>
                )}
              </div>
            </div>
            {q.over_time && (
              <p className="mt-2 text-xs text-ink-2">
                You ran over this time. In the exam, move on when the time for a question is up and come back if you can.
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
