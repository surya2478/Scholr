"use client";

import Link from "next/link";
import type { Reinforcement, SubjectStanding } from "@/lib/api";
import { Card, Chip, Empty } from "@/components/ui";
import { minutes, shortDate } from "@/lib/format";

// What an external class pointed at, in the subject Scholr actually teaches. Never a link back into the
// external course — Scholr complements that programme, it does not repeat it (docs/PHASE-3.md §1).
export function ReinforcementList({
  targets,
  subtitle,
  emptyText,
}: {
  targets: Reinforcement[];
  subtitle: string;
  emptyText: string;
}) {
  return (
    <Card title="🎯 Cambridge IGCSE Topics to Reinforce" subtitle={subtitle} tone="purple">
      {targets.length === 0 && <Empty>{emptyText}</Empty>}
      <ul className="flex flex-col gap-3">
        {targets.map((t) => (
          <li
            key={t.objective_id}
            className="flex flex-col gap-2 rounded-2xl border-2 border-purple-100 bg-white p-4.5 shadow-2xs hover:border-purple-300 transition-colors"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={t.depth === 0 ? "brand" : "warn"}>
                {t.depth === 0 ? "Core Concept" : "Foundation Groundwork"}
              </Chip>
              <span className="text-sm font-fun font-bold text-slate-900">
                {t.objective_code} {t.objective_statement}
              </span>
              <span className="text-xs font-semibold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-md border border-purple-100">
                {t.subject_name}
              </span>
            </div>
            <p className="text-xs text-slate-600 font-medium leading-relaxed">{t.reason}</p>
            {t.note && <p className="text-[11px] text-slate-400 font-medium">{t.note}</p>}
            {t.practicable ? (
              <Link
                href={`/student/practice?subject=${t.subject_id}&objective=${t.objective_id}`}
                className="w-fit text-xs font-fun font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 px-3.5 py-1.5 rounded-xl shadow-xs shadow-blue-600/20 transition-all flex items-center gap-1.5 hover:scale-105"
              >
                <span>Practise this topic now</span>
                <span>→</span>
              </Link>
            ) : (
              <span className="text-xs text-slate-400 font-medium italic">
                📖 Revise this from the {t.subject_name} course book — Scholr has no practice questions for it yet.
              </span>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function StandingCards({ subjects }: { subjects: SubjectStanding[] }) {
  if (subjects.length === 0) return <Empty>No IIT Foundation classes logged yet.</Empty>;
  return (
    <div className="grid gap-3.5 md:grid-cols-2">
      {subjects.map((s) => {
        const covered = s.lessons_total ? Math.round((s.lessons_covered / s.lessons_total) * 100) : 0;
        return (
          <div
            key={s.subject_id}
            className="flex flex-col gap-2.5 rounded-2xl border-2 border-purple-100 bg-white p-4.5 shadow-2xs hover:border-purple-300 transition-all"
          >
            <div className="flex items-center justify-between">
              <div className="text-sm font-fun font-bold text-slate-900">{s.subject_name}</div>
              <span className="text-xs font-fun font-bold text-purple-700 bg-purple-100 px-2.5 py-0.5 rounded-full border border-purple-200">
                {covered}% covered
              </span>
            </div>
            <div className="text-xs text-slate-500 font-medium">
              {s.sessions} session{s.sessions === 1 ? "" : "s"} · {minutes(s.minutes)}
              {s.last_seen_on ? ` · last on ${shortDate(s.last_seen_on)}` : ""}
              {s.accuracy !== null ? ` · ${Math.round(s.accuracy * 100)}% accuracy` : ""}
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-purple-100/70">
              <div
                className="h-full rounded-full bg-gradient-to-r from-purple-500 via-indigo-500 to-amber-500 transition-all"
                style={{ width: `${covered}%` }}
              />
            </div>
            <div className="text-xs font-bold text-slate-700">
              {s.lessons_covered} of {s.lessons_total} lessons logged
            </div>
            {!s.traceable && (
              <p className="text-[11px] text-slate-500 font-medium">
                No IGCSE counterpart yet — Scholr keeps the record, and suggestions appear once it teaches this subject.
              </p>
            )}
            {s.weak_lessons.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {s.weak_lessons.slice(0, 4).map((lesson) => (
                  <span
                    key={lesson.objective_id}
                    className="rounded-xl bg-amber-50 border border-slate-200 px-2.5 py-1 text-[11px] font-bold text-amber-800"
                    title={`${lesson.sessions} session(s), last on ${lesson.last_seen_on}`}
                  >
                    ⚠️ {lesson.title}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
