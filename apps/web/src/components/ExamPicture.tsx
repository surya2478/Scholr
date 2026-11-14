"use client";

import Link from "next/link";
import type { Readiness, Stream } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, Chip } from "./ui";

// One honest exam picture per subject (improvement 10). Everything comes from GET /subjects/{id}/readiness:
// days to the exam, the syllabus met and secure, and the weakest assessment objective — named only once there is
// enough marked work to judge it. No grade: Cambridge sets new boundaries for every paper in every series, and a
// grade estimate means nothing until she has sat several full papers.
function months(days: number): string {
  if (days < 45) return `${days} days`;
  return `about ${Math.round(days / 30.4)} months`;
}

function SubjectExam({ subjectId }: { subjectId: string }) {
  const r = useApi<Readiness>(`/subjects/${subjectId}/readiness`).data;
  if (!r) return null;
  const metShare = r.objectives_total ? (r.objectives_met / r.objectives_total) * 100 : 0;
  const secureShare = r.objectives_total ? (r.objectives_secure / r.objectives_total) * 100 : 0;
  const weakest = r.skills.find((s) => s.skill_code === r.weakest_skill);
  const examMonth = r.exam_session
    ? new Date(`${r.exam_session}-15T00:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : null;

  return (
    <li className="space-y-3 rounded-2xl border border-line-soft bg-tile p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-base font-bold text-ink">{r.subject_name}</span>
        {r.days_to_exam !== null && examMonth && (
          <span className="text-xs font-semibold text-ink-2">
            Exam {examMonth} · <b>{months(r.days_to_exam)}</b> away
          </span>
        )}
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-ink-2">
          <span>
            Syllabus: <b>{r.objectives_met}</b> of {r.objectives_total} topics met · <b>{r.objectives_secure}</b> secure
          </span>
        </div>
        <div className="relative h-2 overflow-hidden rounded-full bg-white" aria-hidden>
          <div className="absolute inset-y-0 left-0 bg-brand-soft" style={{ width: `${metShare}%` }} />
          <div className="absolute inset-y-0 left-0 bg-good" style={{ width: `${secureShare}%` }} />
        </div>
        <p className="text-[11px] text-muted">Secure means shown in marked answers, never from reading alone.</p>
      </div>

      <div className="text-xs text-ink-2">
        {weakest ? (
          <>
            Exam skill to work on: <Chip tone="warn">{weakest.skill_code}</Chip> {weakest.skill_name}
          </>
        ) : (
          <>Exam skills: not judged yet. Each needs about 20 marks of marked answers before anything is said.</>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-2">
        <span>
          Timed papers sat: <b>{r.papers_sat}</b> of {r.papers_available}
        </span>
        <Link href={`/student/learn/subject/${r.subject_id}/past-papers`} className="font-semibold text-brand hover:underline">
          Past papers →
        </Link>
      </div>
      {r.next_step && <p className="text-xs font-medium text-ink">{r.next_step}</p>}
    </li>
  );
}

export function ExamPicture() {
  const streams = useApi<Stream[]>("/learn/streams");
  const taught = (streams.data ?? []).flatMap((s) => s.subjects).filter((x) => x.stage === "taught");
  if (taught.length === 0) return null;
  return (
    <Card
      title="Your exams"
      subtitle="Where you stand, honestly. No grade is shown: that needs several full papers sat against real boundaries."
    >
      <ul className="grid gap-3 md:grid-cols-2">
        {taught.map((x) => (
          <SubjectExam key={x.id} subjectId={x.id} />
        ))}
      </ul>
    </Card>
  );
}
