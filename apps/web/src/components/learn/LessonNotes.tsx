"use client";

import { useEffect, useMemo, useState } from "react";
import { ConceptDialogue } from "@/components/learn/ConceptDialogue";
import { LessonDiagram } from "@/components/learn/diagrams/LessonDiagram";
import { ExploreWithAI } from "@/components/learn/ExploreWithAI";
import { Sources } from "@/components/learn/Sources";
import { WorkedExample } from "@/components/learn/WorkedExample";
import { MathText } from "@/components/MathText";
import type { Lesson } from "@/lib/api";

// A lesson laid out as revision notes (lesson v5/v6): each section with its definition, bullet points and exam tip,
// and the tables, diagrams and worked examples that belong to it placed right under it; then how to write the
// answers, the terminology and the traps. Lessons written on v4 (prose body) are automatically broken into
// scannable revision bullets so she never hits a wall of text.
//
// Everything shown here comes from the lesson itself. "Read ✓" is her own note of which sections she has been
// through, kept on this device; it is not mastery, which only marked answers can show (docs/PRINCIPLES.md).

type Section = Lesson["sections"][number];
type Explore = { subjectId: string; objectiveId: string } | null;

const READ_KEY = (objectiveId: string) => `scholr:topic-read:v1:${objectiveId}`;

/**
 * Splits a dense paragraph body into clean, scannable revision sentences while keeping
 * inline LaTeX ($...$) and abbreviations (e.g., i.e., Fig., p.) intact.
 */
function proseToBullets(body: string): { leadDefinition: string | null; bullets: string[] } {
  const trimmed = body.trim();
  if (!trimmed) return { leadDefinition: null, bullets: [] };

  // Protect LaTeX blocks from sentence splitting
  const mathTokens: string[] = [];
  const masked = trimmed.replace(/\$[^$]+\$/g, (m) => {
    mathTokens.push(m);
    return `__MATH_${mathTokens.length - 1}__`;
  });

  const restore = (s: string) => s.replace(/__MATH_(\d+)__/g, (_, idx) => mathTokens[Number(idx)] ?? "");

  const rawSentences = masked
    .split(/(?<=[.!?])\s+(?=[A-Z0-9$])/g)
    .map((s) => restore(s.trim()))
    .filter(Boolean);

  if (rawSentences.length <= 1) {
    return { leadDefinition: null, bullets: [trimmed] };
  }

  // If the first sentence reads like a formal definition ("A force is...", "The Highest Common Factor (HCF) ... is...")
  const first = rawSentences[0];
  const isDef =
    /^(?:A|An|The)\s+[^.]{2,65}\s+(?:is|are|refers to|means|states that|defines)\b/i.test(first) &&
    first.length < 240;

  if (isDef && rawSentences.length >= 2) {
    return { leadDefinition: first, bullets: rawSentences.slice(1) };
  }

  return { leadDefinition: null, bullets: rawSentences };
}

function sectionContent(section: Section) {
  const parsed = section.points.length === 0 ? proseToBullets(section.body) : null;
  return {
    definition: section.definition || parsed?.leadDefinition || "",
    bullets: section.points.length > 0 ? section.points : (parsed?.bullets ?? []),
  };
}

/**
 * A lesson table, readable as-is, with two ways to test herself on it — both built only from the table's own cells:
 * hide the cells and reveal them one by one, or sort each cell back into its column.
 */
function LessonTable({ table }: { table: Lesson["tables"][number] }) {
  const [mode, setMode] = useState<"read" | "recall" | "sort">("read");
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  const [cardIndex, setCardIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);

  const canSort = table.columns.length >= 3 && table.rows.length >= 2;
  const cards = useMemo(() => {
    if (!canSort) return [];
    const out: { feature: string; text: string; col: number }[] = [];
    table.rows.forEach((row) => {
      for (let c = 1; c < table.columns.length; c++) {
        if (row[c]) out.push({ feature: row[0] ?? "", text: row[c], col: c });
      }
    });
    // Interleave the columns so the answer isn't always the same one in a row.
    return out.sort((a, b) => a.text.length - b.text.length);
  }, [canSort, table.columns, table.rows]);
  const card = cards[cardIndex];

  return (
    <figure className="flex flex-col gap-2.5 rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="text-sm font-bold text-slate-900">📊 {table.title}</figcaption>
        <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1 text-[11px] font-bold">
          {(
            [
              ["read", "Read"],
              ["recall", "Hide & recall"],
              ...(canSort ? [["sort", `Sort the cells (${cards.length})`]] : []),
            ] as [typeof mode, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => {
                setMode(key);
                setRevealed({});
                setCardIndex(0);
                setScore(0);
                setPicked(null);
              }}
              className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                mode === key ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {mode === "sort" && canSort ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
          {card ? (
            <>
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span>
                  {cardIndex + 1} of {cards.length} · <strong className="text-slate-900">{card.feature}</strong>
                </span>
                <span className="font-mono font-bold">
                  {score} correct
                </span>
              </div>
              <p className="rounded-xl border border-slate-200 bg-white p-3 text-center text-sm font-bold text-slate-900">
                <MathText text={card.text} />
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {table.columns.slice(1).map((name, i) => {
                  const col = i + 1;
                  const right = col === card.col;
                  return (
                    <button
                      key={col}
                      type="button"
                      disabled={picked !== null}
                      onClick={() => {
                        setPicked(col);
                        if (right) setScore((s) => s + 1);
                      }}
                      className={`rounded-xl border-2 px-3 py-2.5 text-xs font-bold transition cursor-pointer ${
                        picked === null
                          ? "border-slate-200 bg-white text-slate-900 hover:border-blue-500"
                          : right
                          ? "border-emerald-600 bg-emerald-600 text-white"
                          : picked === col
                          ? "border-rose-600 bg-rose-600 text-white"
                          : "border-slate-200 bg-slate-100 text-slate-400"
                      }`}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
              {picked !== null && (
                <button
                  type="button"
                  onClick={() => {
                    setPicked(null);
                    setCardIndex((i) => i + 1);
                  }}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-500 cursor-pointer"
                >
                  Next →
                </button>
              )}
            </>
          ) : (
            <div className="text-center space-y-2 py-2">
              <p className="text-sm font-bold text-slate-900">
                {score} of {cards.length} sorted correctly
              </p>
              <button
                type="button"
                onClick={() => {
                  setCardIndex(0);
                  setScore(0);
                }}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-blue-500 cursor-pointer"
              >
                Try again ↺
              </button>
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full min-w-[20rem] border-collapse text-sm">
            <thead className="bg-slate-100 text-left text-xs font-bold uppercase tracking-wide text-slate-700">
              <tr>
                {table.columns.map((c, i) => (
                  <th key={i} className="border-b border-slate-200 px-3 py-2">
                    <MathText text={c} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, r) => (
                <tr key={r} className={r % 2 ? "bg-slate-50/70" : "bg-white"}>
                  {row.map((cell, c) => {
                    const hidden = mode === "recall" && c > 0 && !revealed[`${r}-${c}`];
                    return (
                      <td
                        key={c}
                        onClick={() => mode === "recall" && c > 0 && setRevealed((p) => ({ ...p, [`${r}-${c}`]: true }))}
                        className={`border-b border-slate-100 px-3 py-2 text-slate-800 ${c === 0 ? "font-semibold" : ""} ${
                          mode === "recall" && c > 0 ? "cursor-pointer" : ""
                        }`}
                      >
                        {hidden ? (
                          <span className="inline-block rounded-md border border-dashed border-blue-300 bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-700">
                            Tap to reveal
                          </span>
                        ) : (
                          <MathText text={cell} />
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Sources sources={table.sources} />
    </figure>
  );
}

function Placed({
  lesson,
  at,
  askHref,
}: {
  lesson: Lesson;
  at: number; // section number from 1; 0 = after all sections
  askHref: ((q: string) => string) | null;
}) {
  const sectionCount = lesson.sections.length;
  const home = (n: number | undefined) => (n && n >= 1 && n <= sectionCount ? n : 0);
  const tables = lesson.tables.filter((t) => home(t.section) === at);
  const pictures = lesson.diagrams.filter((d) => home(d.sections[0]) === at);
  const examples = lesson.worked_examples
    .map((ex, index) => ({ ex, index }))
    .filter(({ ex }) => home(ex.section) === at);
  if (!tables.length && !pictures.length && !examples.length) return null;
  return (
    <div className="flex flex-col gap-3">
      {pictures.map((d, i) => (
        <LessonDiagram key={`d${i}`} diagram={d} />
      ))}
      {tables.map((t, i) => (
        <LessonTable key={`t${i}`} table={t} />
      ))}
      {examples.map(({ ex, index }) => (
        <WorkedExample key={`e${index}`} example={ex} index={index} askHref={askHref} />
      ))}
    </div>
  );
}

function SectionNotes({
  section,
  number,
  active,
  explore,
  read,
  onToggleRead,
}: {
  section: Section;
  number: number;
  active: boolean;
  explore: Explore;
  read: boolean;
  onToggleRead: () => void;
}) {
  const { definition, bullets } = sectionContent(section);

  return (
    <div
      id={`lesson-section-${number - 1}`}
      data-section-index={number - 1}
      className={`scroll-mt-28 flex flex-col gap-3 rounded-2xl border p-4 md:p-5 transition-colors duration-300 ${
        active ? "border-blue-400 bg-blue-50/40" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className={`flex h-7 w-7 flex-none items-center justify-center rounded-lg text-xs font-bold ${
              read ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-700"
            }`}
          >
            {read ? "✓" : number}
          </span>
          <h3 className="text-base md:text-lg font-bold text-slate-900">{section.heading}</h3>
        </div>
        <button
          type="button"
          onClick={onToggleRead}
          className={`flex-none rounded-lg px-2.5 py-1 text-[11px] font-bold transition cursor-pointer ${
            read
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200"
          }`}
        >
          {read ? "Read ✓" : "Mark as read"}
        </button>
      </div>

      <div className="flex flex-col gap-3 max-w-prose">
        {definition && (
          <div className="rounded-xl border-l-4 border-blue-600 bg-blue-50/80 px-3.5 py-2.5 text-sm text-slate-900">
            <span className="mr-1.5 inline-block rounded bg-blue-100 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-800">
              Definition
            </span>
            <MathText text={definition} className="inline font-semibold" />
          </div>
        )}

        {section.formula_notes && (
          <div className="rounded-xl border border-sky-200 bg-sky-50/80 p-3 text-sm">
            <div className="mb-1 text-[11px] font-bold uppercase tracking-wide text-sky-900">📐 Formula &amp; conditions</div>
            <MathText text={section.formula_notes} className="leading-relaxed text-slate-800" />
          </div>
        )}

        {bullets.length > 0 ? (
          <ul className="ml-5 list-disc space-y-2 text-[15px] leading-relaxed text-slate-800 marker:text-blue-600">
            {bullets.map((p, i) => (
              <li key={i}>
                <MathText text={p} />
              </li>
            ))}
          </ul>
        ) : (
          <MathText text={section.body} className="text-[15px] leading-relaxed text-slate-800" />
        )}

        {section.mental_model && (
          <div className="rounded-xl border border-purple-200 bg-purple-50/70 px-3.5 py-2.5 text-sm">
            <span className="mr-1.5 text-[11px] font-bold uppercase tracking-wide text-purple-900">🧠 Think of it like</span>
            <MathText text={section.mental_model} className="inline text-slate-800" />
          </div>
        )}

        {section.exam_tip && (
          <div className="rounded-xl border border-amber-300 bg-amber-50 px-3.5 py-2.5 text-sm">
            <span className="mr-1.5 text-[11px] font-bold uppercase tracking-wide text-amber-900">⚠️ Exam tip</span>
            <MathText text={section.exam_tip} className="inline text-slate-800" />
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100">
        <Sources sources={section.sources} />
        {explore && (
          <ExploreWithAI
            subjectId={explore.subjectId}
            objectiveId={explore.objectiveId}
            heading={section.heading}
            question={`Explain "${section.heading}" in this topic with a clear example.`}
          />
        )}
      </div>
    </div>
  );
}

function CheatSheetView({ lesson }: { lesson: Lesson }) {
  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4 md:p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">⚡ Quick revise</span>
          <h3 className="text-base font-bold text-slate-900">The whole topic on one page</h3>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-bold text-slate-700">
          {lesson.sections.length} ideas · {lesson.key_terms.length} terms
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {lesson.sections.map((s, i) => {
          const { definition, bullets } = sectionContent(s);
          return (
            <div key={i} className="rounded-xl border border-slate-200 p-3.5 space-y-1.5">
              <div className="text-xs font-bold text-slate-900">
                {i + 1}. {s.heading}
              </div>
              <div className="text-xs text-slate-700 leading-relaxed">
                <MathText text={definition || bullets[0] || s.body} />
              </div>
              {s.formula_notes && (
                <div className="rounded-lg bg-sky-50 px-2.5 py-1.5 text-[11px] text-sky-950 border border-sky-200">
                  <MathText text={s.formula_notes} />
                </div>
              )}
              {s.exam_tip && (
                <div className="rounded-lg bg-amber-50 px-2.5 py-1.5 text-[11px] text-amber-950 border border-amber-200">
                  ⚠️ <MathText text={s.exam_tip} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {lesson.diagrams.map((d, i) => (
        <LessonDiagram key={i} diagram={d} />
      ))}
      {lesson.tables.map((t, i) => (
        <LessonTable key={i} table={t} />
      ))}

      {lesson.pitfalls.length > 0 && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/70 p-3.5">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wider text-amber-900">⚠️ Traps</h4>
          <ul className="ml-4 list-disc space-y-1 text-xs text-slate-800">
            {lesson.pitfalls.map((p, i) => (
              <li key={i}>
                <MathText text={p} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Which section is on screen, for the outline. */
function useSectionInView(count: number, enabled: boolean): number | null {
  const [current, setCurrent] = useState<number | null>(null);
  useEffect(() => {
    if (!enabled || count === 0) return;
    const nodes = Array.from(document.querySelectorAll<HTMLElement>("[data-section-index]"));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (visible.length === 0) return;
        const top = visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
        setCurrent(Number(top.target.getAttribute("data-section-index")));
      },
      { rootMargin: "-20% 0px -60% 0px" },
    );
    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [count, enabled]);
  return current;
}

export function LessonNotes({
  objectiveId,
  lesson,
  askHref,
  explore,
  activeSectionIndex,
  onReadCountChange,
}: {
  objectiveId: string;
  lesson: Lesson;
  askHref: ((q: string) => string) | null;
  explore: Explore;
  activeSectionIndex: number | null;
  onReadCountChange?: (read: number, total: number) => void;
}) {
  const [viewMode, setViewMode] = useState<"notes" | "quick">("notes");
  const [read, setRead] = useState<Set<number>>(new Set());
  const [unlocked, setUnlocked] = useState<Record<number, number>>({});
  const total = lesson.sections.length;

  // Her "read" ticks for this topic, kept on this device.
  useEffect(() => {
    try {
      const saved = JSON.parse(window.localStorage.getItem(READ_KEY(objectiveId)) ?? "[]") as number[];
      setRead(new Set(saved.filter((n) => n >= 0 && n < total)));
    } catch {
      setRead(new Set());
    }
  }, [objectiveId, total]);

  useEffect(() => {
    onReadCountChange?.(read.size, total);
  }, [read, total, onReadCountChange]);

  function toggleRead(idx: number) {
    setRead((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      try {
        window.localStorage.setItem(READ_KEY(objectiveId), JSON.stringify(Array.from(next)));
      } catch {
        // storage full or blocked: the ticks still work for this visit
      }
      return next;
    });
  }

  const inView = useSectionInView(total, viewMode === "notes");
  const highlighted = activeSectionIndex ?? inView;

  function goTo(idx: number) {
    document.getElementById(`lesson-section-${idx}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const outline = (
    <nav aria-label="On this page" className="flex flex-col gap-0.5">
      <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold uppercase tracking-wider text-slate-500">
        <span>On this page</span>
        <span className="font-mono normal-case tracking-normal">
          {read.size}/{total} read
        </span>
      </div>
      <div className="mb-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full bg-emerald-500 transition-all duration-300"
          style={{ width: `${total ? (read.size / total) * 100 : 0}%` }}
        />
      </div>
      {lesson.sections.map((s, i) => (
        <button
          key={i}
          type="button"
          onClick={() => goTo(i)}
          className={`flex items-start gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition cursor-pointer ${
            highlighted === i ? "bg-blue-50 font-bold text-blue-900" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
          }`}
        >
          <span className={`w-4 flex-none font-mono ${read.has(i) ? "text-emerald-600" : "text-slate-400"}`}>
            {read.has(i) ? "✓" : i + 1}
          </span>
          <span className="line-clamp-2">{s.heading}</span>
        </button>
      ))}
      {lesson.exam_answers.length > 0 && (
        <button
          type="button"
          onClick={() => document.getElementById("lesson-exam-answers")?.scrollIntoView({ behavior: "smooth" })}
          className="mt-1 rounded-lg px-2 py-1.5 text-left text-xs text-slate-600 hover:bg-slate-50 cursor-pointer"
        >
          🎯 How to answer
        </button>
      )}
      {(lesson.key_terms.length > 0 || lesson.pitfalls.length > 0) && (
        <button
          type="button"
          onClick={() => document.getElementById("lesson-terms")?.scrollIntoView({ behavior: "smooth" })}
          className="rounded-lg px-2 py-1.5 text-left text-xs text-slate-600 hover:bg-slate-50 cursor-pointer"
        >
          📘 Terms &amp; traps
        </button>
      )}
    </nav>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1 rounded-xl bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setViewMode("notes")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
              viewMode === "notes" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            📖 Notes
          </button>
          <button
            type="button"
            onClick={() => setViewMode("quick")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
              viewMode === "quick" ? "bg-white text-slate-900 shadow-2xs" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            ⚡ Quick revise
          </button>
        </div>
      </div>

      {viewMode === "quick" ? (
        <CheatSheetView lesson={lesson} />
      ) : (
        <div className="lg:grid lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-6">
          {/* Outline: sticky left rail on large screens, a scrolling chip strip on small ones */}
          <aside className="hidden lg:block">
            <div className="sticky top-24">{outline}</div>
          </aside>
          <div className="lg:hidden sticky top-14 z-10 -mx-1 mb-3 flex gap-1.5 overflow-x-auto bg-white/95 px-1 py-2 backdrop-blur">
            {lesson.sections.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => goTo(i)}
                className={`flex-none rounded-full border px-3 py-1 text-[11px] font-bold cursor-pointer ${
                  highlighted === i
                    ? "border-blue-600 bg-blue-600 text-white"
                    : read.has(i)
                    ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                    : "border-slate-200 bg-white text-slate-700"
                }`}
              >
                {read.has(i) ? "✓ " : `${i + 1}. `}
                {s.heading.length > 28 ? `${s.heading.slice(0, 28)}…` : s.heading}
              </button>
            ))}
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            {lesson.introduction && (
              <div className="max-w-prose rounded-2xl border border-violet-200 bg-violet-50/60 p-4 text-[15px] leading-relaxed text-slate-800">
                <h3 className="mb-1 text-sm font-bold text-violet-900">Why this topic matters</h3>
                <MathText text={lesson.introduction} />
              </div>
            )}

            {lesson.sections.map((section, i) => (
              <div key={i} className="flex flex-col gap-3">
                <SectionNotes
                  section={section}
                  number={i + 1}
                  active={activeSectionIndex === i}
                  explore={explore}
                  read={read.has(i)}
                  onToggleRead={() => toggleRead(i)}
                />
                <Placed lesson={lesson} at={i + 1} askHref={askHref} />
              </div>
            ))}
            <Placed lesson={lesson} at={0} askHref={askHref} />

            {lesson.exam_answers.length > 0 && (
              <div id="lesson-exam-answers" className="scroll-mt-28 rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4 md:p-5 space-y-3">
                <div>
                  <h3 className="font-bold text-indigo-950">🎯 How to answer in the exam</h3>
                  <p className="text-xs text-slate-600">
                    One clear point per mark. Try to say the next point yourself before you reveal it.
                  </p>
                </div>
                {lesson.exam_answers.map((a, i) => {
                  const shown = unlocked[i] ?? 1;
                  return (
                    <div key={i} className="rounded-xl border border-indigo-100 bg-white p-4 space-y-2.5">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <p className="text-sm font-semibold text-slate-900 max-w-prose">
                          <span className="mr-1 text-indigo-600">Q.</span>
                          <MathText text={a.question} className="inline" />
                        </p>
                        {shown < a.points.length && (
                          <button
                            type="button"
                            onClick={() => setUnlocked((p) => ({ ...p, [i]: a.points.length }))}
                            className="text-xs font-bold text-indigo-700 hover:underline cursor-pointer"
                          >
                            Show all {a.points.length}
                          </button>
                        )}
                      </div>
                      <ol className="ml-5 list-decimal space-y-1.5 text-sm text-slate-800 max-w-prose">
                        {a.points.slice(0, shown).map((p, j) => (
                          <li key={j}>
                            <MathText text={p} />
                          </li>
                        ))}
                      </ol>
                      {shown < a.points.length && (
                        <button
                          type="button"
                          onClick={() => setUnlocked((p) => ({ ...p, [i]: shown + 1 }))}
                          className="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-800 hover:bg-indigo-100 cursor-pointer"
                        >
                          Reveal point {shown + 1} of {a.points.length}
                        </button>
                      )}
                      <Sources sources={a.sources} />
                    </div>
                  );
                })}
              </div>
            )}

            {(lesson.key_terms.length > 0 || lesson.pitfalls.length > 0) && (
              <div id="lesson-terms" className="scroll-mt-28 grid grid-cols-1 gap-4 xl:grid-cols-2">
                {lesson.key_terms.length > 0 && (
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <h3 className="mb-2 font-bold text-slate-900">📘 Key terms</h3>
                    <p className="mb-2 text-[11px] text-slate-500">To test yourself on these, use the Flashcards tab.</p>
                    <dl className="divide-y divide-slate-100 text-sm">
                      {lesson.key_terms.map((t, i) => (
                        <div key={i} className="py-1.5">
                          <dt className="font-semibold text-slate-900">
                            <MathText text={t.term} />
                          </dt>
                          <dd className="text-slate-700">
                            <MathText text={t.meaning} />
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
                {lesson.pitfalls.length > 0 && (
                  <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4">
                    <h3 className="mb-2 font-bold text-amber-950">⚠️ Traps to avoid</h3>
                    <ul className="ml-5 list-disc space-y-1.5 text-sm text-slate-800">
                      {lesson.pitfalls.map((p, i) => (
                        <li key={i}>
                          <MathText text={p} />
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {lesson.podcast_script && lesson.podcast_script.length > 0 && (
              <ConceptDialogue script={lesson.podcast_script} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
