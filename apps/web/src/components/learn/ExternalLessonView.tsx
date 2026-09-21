"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ExternalLesson } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { Button, Card, Chip, Empty, ErrorNote } from "../ui";
import { TryQuestion } from "./TryQuestion";

// An IIT Foundation lesson (docs/STUDENT-APP.md step 5). Scholr never teaches it: it records her classes, shows the
// IGCSE ground underneath, and warms her up from that ground before the next class.
const KINDS = [
  { value: "class", label: "Class" },
  { value: "test", label: "Test" },
  { value: "homework", label: "Homework" },
];

function LogClass({
  subjectId,
  objectiveId,
  title,
  onLogged,
}: {
  subjectId: string;
  objectiveId: string;
  title: string;
  onLogged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState("class");
  const [day, setDay] = useState(() => new Date().toISOString().slice(0, 10));
  const [score, setScore] = useState("");
  const [outOf, setOutOf] = useState("");
  const [hard, setHard] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (!open) {
    return (
      <Button variant="secondary" className="self-start" onClick={() => setOpen(true)}>
        + Log a class on this lesson
      </Button>
    );
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const marks = score !== "" && outOf !== "" ? { score: Number(score), max_score: Number(outOf) } : {};
    try {
      await api("/external-training", {
        method: "POST",
        json: {
          subject_id: subjectId,
          kind,
          title,
          occurred_on: day,
          objective_ids: [objectiveId],
          weak_objective_ids: hard ? [objectiveId] : [],
          ...marks,
        },
      });
      setOpen(false);
      setScore("");
      setOutOf("");
      setHard(false);
      onLogged();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-3 rounded-2xl border border-purple-200 bg-white p-4 text-sm">
      <div className="flex flex-wrap gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-slate-500">What</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)} className="rounded-xl border border-slate-200 px-3 py-2">
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-slate-500">When</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="rounded-xl border border-slate-200 px-3 py-2" required />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs font-semibold text-slate-500">Marks (if any)</span>
          <span className="flex items-center gap-1">
            <input type="number" min={0} value={score} onChange={(e) => setScore(e.target.value)} className="w-20 rounded-xl border border-slate-200 px-3 py-2" />
            <span className="text-slate-400">out of</span>
            <input type="number" min={1} value={outOf} onChange={(e) => setOutOf(e.target.value)} className="w-20 rounded-xl border border-slate-200 px-3 py-2" />
          </span>
        </label>
      </div>
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={hard} onChange={(e) => setHard(e.target.checked)} />
        <span>I found this lesson hard</span>
      </label>
      {error ? <ErrorNote error={error} /> : null}
      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function ExternalLessonView({
  lesson,
  subjectId,
  objectiveId,
  title,
  onChanged,
}: {
  lesson: ExternalLesson;
  subjectId: string;
  objectiveId: string;
  title: string;
  onChanged: () => void;
}) {
  return (
    <>
      <Card title="🏫 Your classes on this lesson" subtitle="Recorded from your IIT Foundation classes" tone="purple">
        {lesson.classes.length === 0 && <Empty>No class on this lesson has been logged yet.</Empty>}
        <ul className="flex flex-col gap-2">
          {lesson.classes.map((c, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium text-slate-800">
                {c.occurred_on} · {c.title}
              </span>
              <span className="flex gap-2">
                {c.score !== null && c.max_score !== null && (
                  <Chip tone="neutral">
                    {c.score}/{c.max_score}
                  </Chip>
                )}
                {c.struggled && <Chip tone="warn">Found it hard</Chip>}
              </span>
            </li>
          ))}
        </ul>
        <LogClass subjectId={subjectId} objectiveId={objectiveId} title={title} onLogged={onChanged} />
      </Card>

      <Card
        title="🧱 The IGCSE ground underneath"
        subtitle="What this lesson rests on in your Cambridge subjects, and you're not yet secure in"
        tone="blue"
      >
        {lesson.ground.length === 0 && (
          <Empty>Nothing to shore up — you&apos;re secure in the IGCSE topics this lesson rests on, or none is mapped yet.</Empty>
        )}
        <ul className="flex flex-col gap-2">
          {lesson.ground.map((g) => (
            <li key={g.objective_id} className="flex flex-col gap-0.5">
              <Link href={`/student/learn/topic/${g.objective_id}`} className="text-sm font-semibold text-slate-900 hover:underline">
                {g.subject_name} · {g.objective_code} {g.statement}
              </Link>
              <span className="text-xs text-slate-500">
                {g.reason}
                {!g.practicable && " Revise this one from your course book — Scholr doesn't set questions on it yet."}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      {lesson.warm_up.length > 0 && (
        <Card title="🔥 Warm-up before class" subtitle="A few IGCSE questions on the ground this lesson stands on" tone="orange">
          {lesson.warm_up.map((item) => (
            <TryQuestion
              key={item.id}
              item={item}
              askHref={(q, questionSubjectId) => tutorHref({ subjectId: questionSubjectId, ask: q })}
            />
          ))}
        </Card>
      )}
    </>
  );
}
