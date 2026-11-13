"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { MasteryBadge, StageChip } from "@/components/learn/Streams";
import { Chip, Empty, ErrorNote } from "@/components/ui";
import type { Chapter, ObjectiveCard, SubjectLearn } from "@/lib/api";
import { useApi } from "@/lib/useApi";

type FilterMode = "all" | "practised" | "secure" | "has_questions" | "struggled";

function collectObjectives(chapter: Chapter): ObjectiveCard[] {
  return [
    ...chapter.objectives,
    ...chapter.chapters.flatMap((c) => collectObjectives(c)),
  ];
}

function matchesObjective(
  o: ObjectiveCard,
  query: string,
  filter: FilterMode,
  external: boolean
): boolean {
  if (query) {
    const q = query.toLowerCase();
    const hit =
      o.code.toLowerCase().includes(q) || o.statement.toLowerCase().includes(q);
    if (!hit) return false;
  }
  if (filter === "practised") {
    return external ? o.classes > 0 : (o.mastery_level ?? 0) >= 1;
  }
  if (filter === "secure") {
    return (o.mastery_level ?? 0) >= 3;
  }
  if (filter === "has_questions") {
    return o.items > 0;
  }
  if (filter === "struggled") {
    return external ? o.struggled : (o.mastery_level ?? 0) === 1 || (o.mastery_level ?? 0) === 2;
  }
  return true;
}

function filterChapter(
  chapter: Chapter,
  query: string,
  filter: FilterMode,
  external: boolean
): Chapter | null {
  const q = query.trim().toLowerCase();
  const chapterNameMatches = q.length > 0 && chapter.name.toLowerCase().includes(q);
  const effectiveQuery = chapterNameMatches ? "" : q;

  const objectives = chapter.objectives.filter((o) =>
    matchesObjective(o, effectiveQuery, filter, external)
  );
  const children = chapter.chapters
    .map((c) => filterChapter(c, effectiveQuery, filter, external))
    .filter((c): c is Chapter => c !== null);

  if (objectives.length === 0 && children.length === 0) {
    return null;
  }
  return { ...chapter, objectives, chapters: children };
}

function ClassChip({ objective }: { objective: ObjectiveCard }) {
  if (objective.classes === 0)
    return <span className="font-mono text-[11px] font-semibold text-slate-400">NO LOGS</span>;
  return (
    <Chip tone={objective.struggled ? "warn" : "neutral"}>
      {objective.classes} class{objective.classes === 1 ? "" : "es"}
      {objective.struggled ? " · flagged" : ""}
    </Chip>
  );
}

function TopicRow({ objective, external }: { objective: ObjectiveCard; external: boolean }) {
  return (
    <div className="group flex flex-wrap items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-slate-50">
      <Link
        href={`/student/learn/topic/${objective.id}`}
        className="flex min-w-0 flex-1 items-center gap-3"
      >
        <span className="w-12 flex-none rounded-lg bg-slate-100 px-2 py-0.5 text-center font-mono text-xs font-bold text-slate-700 group-hover:bg-blue-600 group-hover:text-white transition-colors">
          {objective.code}
        </span>
        <span className="min-w-0 flex-1 text-sm font-medium text-slate-800 group-hover:text-blue-700">
          {objective.statement}
        </span>
      </Link>

      <div className="flex flex-wrap items-center gap-2">
        {!external && objective.lesson === "ready" && (
          <Link
            href={`/student/learn/topic/${objective.id}#notes`}
            className="rounded-lg bg-blue-50 border border-blue-200 px-2.5 py-1 text-[11px] font-bold text-blue-800 hover:bg-blue-100 transition"
          >
            📖 Revision Notes
          </Link>
        )}
        {!external && (objective.items > 0 || objective.lesson === "ready") && (
          <Link
            href={`/student/learn/topic/${objective.id}#easy-1`}
            className="rounded-lg bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-[11px] font-bold text-emerald-800 hover:bg-emerald-100 transition"
          >
            ✍️ Topic Questions{objective.items > 0 ? ` (${objective.items})` : ""}
          </Link>
        )}
        {external ? (
          <ClassChip objective={objective} />
        ) : objective.school_led ? (
          <Chip tone="neutral">School-led</Chip>
        ) : (
          <MasteryBadge level={objective.mastery_level} name={objective.mastery_name} />
        )}
      </div>
    </div>
  );
}

function ChapterBlock({
  chapter,
  depth,
  external,
  forceOpen,
}: {
  chapter: Chapter;
  depth: number;
  external: boolean;
  forceOpen: boolean;
}) {
  const [manualOpen, setManualOpen] = useState<boolean | null>(null);
  const open = manualOpen !== null ? manualOpen : forceOpen;

  const allObjectives = useMemo(() => collectObjectives(chapter), [chapter]);
  const total = allObjectives.length;
  if (total === 0) return null;

  const practisedCount = allObjectives.filter((o) =>
    external ? o.classes > 0 : (o.mastery_level ?? 0) >= 1
  ).length;
  const secureCount = allObjectives.filter((o) => (o.mastery_level ?? 0) >= 3).length;
  const totalQuestions = allObjectives.reduce((acc, o) => acc + o.items, 0);
  const pct = Math.round(((external ? practisedCount : secureCount || practisedCount) / total) * 100);

  if (depth === 0 && chapter.chapters.length > 0) {
    return (
      <div className="flex flex-col gap-2.5 pt-2">
        <div className="flex items-center justify-between px-1">
          <h2 className="font-mono text-xs font-bold uppercase tracking-wider text-slate-500">
            {chapter.name}
          </h2>
          <span className="font-mono text-[11px] font-semibold text-slate-400">
            {total} topics
          </span>
        </div>
        {chapter.objectives.map((o) => (
          <TopicRow key={o.id} objective={o} external={external} />
        ))}
        {chapter.chapters.map((c) => (
          <ChapterBlock
            key={c.id}
            chapter={c}
            depth={depth + 1}
            external={external}
            forceOpen={forceOpen}
          />
        ))}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs transition hover:border-blue-400">
      <button
        type="button"
        onClick={() => setManualOpen(!open)}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3.5 text-left cursor-pointer"
        aria-expanded={open}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2.5">
          <span className="font-extrabold text-slate-900">{chapter.name}</span>
          {practisedCount > 0 && (
            <span className="rounded-md bg-emerald-50 border border-emerald-200 px-2 py-0.5 font-mono text-[11px] font-bold text-emerald-800">
              {external
                ? `${practisedCount}/${total} logged`
                : secureCount > 0
                ? `${secureCount}/${total} secure`
                : `${practisedCount}/${total} started`}
            </span>
          )}
        </div>

        <div className="flex items-center gap-3 text-xs font-semibold text-slate-500">
          {!external && totalQuestions > 0 && (
            <span className="hidden sm:inline font-mono text-[11px] text-slate-400">
              {totalQuestions} past-paper Qs
            </span>
          )}
          {practisedCount > 0 && (
            <div className="hidden sm:block h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          )}
          <span className="font-mono text-xs">
            {total} topic{total === 1 ? "" : "s"}
          </span>
          <span className={`inline-block transition-transform ${open ? "rotate-90" : ""}`}>
            ›
          </span>
        </div>
      </button>
      {open && (
        <div className="flex flex-col divide-y divide-slate-100 border-t border-slate-100 px-2 py-1.5">
          {chapter.objectives.map((o) => (
            <TopicRow key={o.id} objective={o} external={external} />
          ))}
          {chapter.chapters.map((c) => (
            <ChapterBlock
              key={c.id}
              chapter={c}
              depth={depth + 1}
              external={external}
              forceOpen={forceOpen}
            />
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
  const external = subject?.stage === "external";

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterMode>("all");
  const [expandAll, setExpandAll] = useState(false);

  const filteredChapters = useMemo(() => {
    const raw = view.data?.chapters ?? [];
    if (!search.trim() && filter === "all") return raw;
    return raw
      .map((c) => filterChapter(c, search, filter, Boolean(external)))
      .filter((c): c is Chapter => c !== null);
  }, [view.data?.chapters, search, filter, external]);

  const forceOpen = expandAll || search.trim().length > 0 || filter !== "all";

  return (
    <div className="space-y-5">
      <Link href="/student/learn" className="text-xs font-bold text-blue-600 hover:underline">
        ← All Syllabus Streams
      </Link>
      {view.error ? <ErrorNote error={view.error} /> : null}
      {subject && (
        <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 text-white shadow-xl space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <StageChip stage={subject.stage} />
                {subject.syllabus_code && (
                  <span className="rounded-md bg-white/10 border border-white/15 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-300">
                    Syllabus {subject.syllabus_code}
                  </span>
                )}
              </div>
              <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
                {subject.name}
              </h1>
              <p className="text-xs text-slate-300 font-medium">
                {subject.secure === null
                  ? `${subject.objectives} syllabus topics ready · revision notes and topic questions`
                  : `${subject.secure} of ${subject.objectives} topics secure · ${subject.practised} topics started`}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {subject.stage === "taught" && (
                <Link
                  href={`/student/learn/subject/${subject.id}/past-papers`}
                  className="rounded-xl bg-emerald-500 hover:bg-emerald-400 px-3.5 py-2 text-xs font-extrabold text-slate-950 shadow-sm transition"
                >
                  📝 Past-Paper Question Hub →
                </Link>
              )}
              {(view.data?.non_calculator_questions ?? 0) > 0 && (
                <Link
                  href={`/student/practice?subject=${subject.id}&no_calculator=1`}
                  title={`${view.data?.non_calculator_questions} questions from Paper 2, which allows no calculator`}
                  className="rounded-xl bg-amber-300 hover:bg-amber-200 px-3.5 py-2 text-xs font-extrabold text-slate-950 shadow-sm transition"
                >
                  ✏️ Practise without a calculator →
                </Link>
              )}
              <button
                type="button"
                onClick={() => setExpandAll((v) => !v)}
                className="rounded-xl border border-white/20 bg-white/10 hover:bg-white/15 px-3.5 py-2 text-xs font-bold text-white cursor-pointer transition"
              >
                {expandAll ? "Collapse chapters ▲" : "Expand all chapters ▼"}
              </button>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-4 border-t border-white/10">
            <div className="relative flex-1">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search topic name or syllabus code (e.g. '1.1', 'quadratic', 'forces', 'positivism')…"
                className="h-10 w-full rounded-xl border border-white/20 bg-white/10 pl-3.5 pr-8 text-xs font-medium text-white placeholder:text-slate-300 outline-none focus:border-emerald-400 focus:bg-white/15"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-300 hover:text-white"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              {(
                external
                  ? [
                      { key: "all", label: "All lessons" },
                      { key: "practised", label: "Logged classes" },
                      { key: "struggled", label: "Flagged hard" },
                    ]
                  : [
                      { key: "all", label: "All topics" },
                      { key: "practised", label: "Started" },
                      { key: "secure", label: "Secure" },
                      ...(subject.stage === "taught"
                        ? [{ key: "has_questions", label: "Has Exam Qs" }]
                        : []),
                    ]
              ).map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setFilter(item.key as FilterMode)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                    filter === item.key
                      ? "bg-blue-500 text-white shadow-2xs"
                      : "border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {filteredChapters.length === 0 && !view.loading && (
          <Empty>
            No topics matched your search or filter.{" "}
            <button
              type="button"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
              className="font-bold text-blue-600 underline ml-1 cursor-pointer"
            >
              Reset filters
            </button>
          </Empty>
        )}
        {filteredChapters.map((chapter) => (
          <ChapterBlock
            key={chapter.id}
            chapter={chapter}
            depth={0}
            external={Boolean(external)}
            forceOpen={forceOpen}
          />
        ))}
      </div>
    </div>
  );
}
