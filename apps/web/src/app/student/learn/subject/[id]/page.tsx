"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { MasteryBadge, StageChip } from "@/components/learn/Streams";
import { Chip, ErrorNote } from "@/components/ui";
import type { Chapter, ObjectiveCard, SubjectLearn } from "@/lib/api";
import { useApi } from "@/lib/useApi";

function countObjectives(chapter: Chapter): number {
  return chapter.objectives.length + chapter.chapters.reduce((n, c) => n + countObjectives(c), 0);
}

function ClassChip({ objective }: { objective: ObjectiveCard }) {
  if (objective.classes === 0) return <span className="text-[11px] font-semibold text-slate-400">No classes logged</span>;
  return (
    <Chip tone={objective.struggled ? "warn" : "neutral"}>
      {objective.classes} class{objective.classes === 1 ? "" : "es"}
      {objective.struggled ? " · found hard" : ""}
    </Chip>
  );
}

function TopicRow({ objective, external }: { objective: ObjectiveCard; external: boolean }) {
  return (
    <Link
      href={`/student/learn/topic/${objective.id}`}
      className="flex items-center gap-3 rounded-xl px-3 py-2.5 transition hover:bg-orange-50"
    >
      <span className="w-12 flex-none text-xs font-bold text-slate-400">{objective.code}</span>
      <span className="flex-1 text-sm font-medium text-slate-800">{objective.statement}</span>
      {external ? (
        <ClassChip objective={objective} />
      ) : objective.school_led ? (
        <Chip tone="neutral">At school for now</Chip>
      ) : (
        <MasteryBadge level={objective.mastery_level} name={objective.mastery_name} />
      )}
    </Link>
  );
}

function ChapterBlock({ chapter, depth, external }: { chapter: Chapter; depth: number; external: boolean }) {
  const [open, setOpen] = useState(false);
  const total = countObjectives(chapter);
  if (total === 0) return null;
  if (depth === 0 && chapter.chapters.length > 0) {
    // A top-level area that groups chapters: a heading, not a fold.
    return (
      <div className="flex flex-col gap-2">
        <h2 className="mt-2 text-sm font-fun font-bold uppercase tracking-wide text-slate-500">{chapter.name}</h2>
        {chapter.objectives.map((o) => (
          <TopicRow key={o.id} objective={o} external={external} />
        ))}
        {chapter.chapters.map((c) => (
          <ChapterBlock key={c.id} chapter={c} depth={depth + 1} external={external} />
        ))}
      </div>
    );
  }
  return (
    <div className="rounded-2xl border-2 border-amber-200/70 bg-white shadow-2xs">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="font-fun font-bold text-slate-900">{chapter.name}</span>
        <span className="flex items-center gap-2 text-xs font-semibold text-slate-500">
          {total} topic{total === 1 ? "" : "s"}
          <span className={`transition-transform ${open ? "rotate-90" : ""}`}>›</span>
        </span>
      </button>
      {open && (
        <div className="flex flex-col border-t border-amber-100 px-1 py-1">
          {chapter.objectives.map((o) => (
            <TopicRow key={o.id} objective={o} external={external} />
          ))}
          {chapter.chapters.map((c) => (
            <ChapterBlock key={c.id} chapter={c} depth={depth + 1} external={external} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function SubjectPage() {
  const { id } = useParams<{ id: string }>();
  const view = useApi<SubjectLearn>(`/learn/subjects/${id}`);
  const subject = view.data?.subject;

  return (
    <div className="space-y-5">
      <Link href="/student/learn" className="text-xs font-bold text-orange-600 hover:underline">
        ← All subjects
      </Link>
      {view.error ? <ErrorNote error={view.error} /> : null}
      {subject && (
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-fun font-bold text-slate-900">{subject.name}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <StageChip stage={subject.stage} />
            {subject.stage === "taught" && (
              <Link
                href={`/student/learn/subject/${subject.id}/past-papers`}
                className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-fun font-bold text-blue-800 hover:bg-blue-100"
              >
                📝 Past-paper questions by chapter
              </Link>
            )}
            <span className="text-xs text-slate-500 font-medium">
              {subject.secure === null
                ? `${subject.objectives} topics — none practised yet`
                : `${subject.secure} of ${subject.objectives} topics secure`}
            </span>
          </div>
        </div>
      )}
      <div className="flex flex-col gap-3">
        {(view.data?.chapters ?? []).map((chapter) => (
          <ChapterBlock key={chapter.id} chapter={chapter} depth={0} external={subject?.stage === "external"} />
        ))}
      </div>
    </div>
  );
}
