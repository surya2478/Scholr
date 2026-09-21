"use client";

import Link from "next/link";
import { useState } from "react";
import { ExaminerInsightsView } from "@/components/ExaminerInsights";
import { MathText } from "@/components/MathText";
import { Chip } from "@/components/ui";
import type { ExamLevel as ExamLevelData } from "@/lib/api";

// The exam level of a topic (docs/STUDENT-APP.md AC-U16): what the exam does with the idea the lesson explained.
// Everything here comes from checked material — the bank's own count of past-paper questions, a real question
// solved from its official mark scheme (answer and marks checked by code, then read by a person), and what the
// examiners wrote about it. The steps open one at a time, like a worked example, so she can try it first.

function list(words: string[]): string {
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

function HowExamined({ how }: { how: NonNullable<ExamLevelData["how_examined"]> }) {
  const years = how.years.length > 1 ? `${how.years[0]}–${how.years[how.years.length - 1]}` : how.years[0];
  const marks = how.marks_min === how.marks_max ? `${how.marks_min}` : `${how.marks_min}–${how.marks_max}`;
  return (
    <p className="text-sm leading-relaxed text-slate-700">
      Asked <strong>{how.asked}</strong> {how.asked === 1 ? "time" : "times"} in the past papers in your bank (
      {years}), on {list(how.papers)}, for {marks} {how.marks_max === 1 ? "mark" : "marks"}.
      {how.command_words.length > 0 && (
        <>
          {" "}
          The question usually says: <em>{list(how.command_words.map((w) => `“${w}”`))}</em>.
        </>
      )}
    </p>
  );
}

function WorkedExam({
  worked,
  askHref,
}: {
  worked: NonNullable<ExamLevelData["worked"]>;
  askHref: ((q: string) => string) | null;
}) {
  const [shown, setShown] = useState(0);
  const total = worked.steps.length;
  const allShown = shown >= total;

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-indigo-200 bg-indigo-50/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-fun font-bold text-indigo-900">A real exam question, solved</h3>
        <div className="flex items-center gap-2">
          <Chip tone="neutral">
            {worked.label} · {worked.marks} {worked.marks === 1 ? "mark" : "marks"}
          </Chip>
          {!allShown && total > 1 && (
            <button onClick={() => setShown(total)} className="text-[11px] font-semibold text-indigo-800 hover:underline">
              Show all steps
            </button>
          )}
        </div>
      </div>

      {worked.context && <MathText text={worked.context} className="text-sm text-slate-700" />}
      <MathText text={worked.stem} className="text-sm font-medium text-slate-900" />
      {worked.has_diagram && (
        <p className="text-[11px] text-slate-500">
          In the paper this question comes with a graph. The steps say what to draw and what to read from it.
        </p>
      )}

      <ol className="ml-5 list-decimal space-y-1.5 text-sm text-slate-700">
        {worked.steps.slice(0, shown).map((step, j) => (
          <li key={j}>
            <span className="flex flex-wrap items-start gap-2">
              <MathText text={step.text} className="flex-1" />
              {step.mark && (
                <span
                  className="shrink-0 rounded-lg bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-800"
                  title="The mark this step earns in the official mark scheme"
                >
                  {step.mark}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
      {!allShown && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setShown(shown + 1)}
            className="rounded-xl border border-indigo-300 bg-white px-3 py-1.5 text-xs font-fun font-bold text-indigo-800 hover:bg-indigo-50"
          >
            {shown === 0 ? "Try it first, then show step 1" : `Show step ${shown + 1}`}
          </button>
          <span className="text-[11px] text-slate-500">
            {total - shown} of {total} steps still hidden
          </span>
        </div>
      )}

      {allShown && (
        <>
          <div className="text-sm font-semibold text-slate-900">
            Answer: <MathText text={worked.final_answer} />
          </div>
          {worked.tip && (
            <p className="rounded-xl bg-white/70 px-3 py-2 text-xs text-slate-700">
              <span className="font-bold text-indigo-900">Where marks go: </span>
              <MathText text={worked.tip} />
            </p>
          )}
          <p className="text-[11px] text-slate-500">
            M marks are for method, A marks for an accurate answer, B marks stand alone. The answer was checked against
            the official mark scheme.
          </p>

          <div className="mt-2 flex flex-col gap-1.5 rounded-xl border border-indigo-200 bg-white p-3 text-xs text-slate-800 shadow-2xs">
            <div className="flex items-center justify-between">
              <span className="font-fun font-bold text-indigo-900">📝 Cambridge Transfer Challenge:</span>
              <span className="text-[10px] text-indigo-700 font-semibold">Real Exam Simulation</span>
            </div>
            <p className="text-slate-700">
              Exam walkthrough completed! Now test whether you can produce the full working under exam conditions: try one of the <strong>Exam questions</strong> below without looking at hints.
            </p>
            <a
              href="#part-exam"
              className="self-start inline-flex items-center gap-1 rounded-lg bg-indigo-700 px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-indigo-800 transition"
            >
              <span>↓ Jump to Exam Questions</span>
            </a>
          </div>
        </>
      )}

      {askHref && (
        <Link
          href={askHref(`${worked.context ?? ""} ${worked.stem}`.trim())}
          className="self-start text-xs font-fun font-bold text-orange-600 hover:underline"
        >
          🦉 Don&apos;t follow a step? Ask the Tutor
        </Link>
      )}
    </div>
  );
}

export function ExamLevel({
  data,
  askHref,
}: {
  data: ExamLevelData;
  askHref: ((q: string) => string) | null;
}) {
  return (
    <div className="flex flex-col gap-3">
      {data.how_examined && <HowExamined how={data.how_examined} />}
      {data.worked ? (
        <WorkedExam worked={data.worked} askHref={askHref} />
      ) : data.solves ? (
        <p className="text-xs text-slate-500">
          A solved exam question appears here once one on this topic has been written and checked.
        </p>
      ) : (
        <p className="text-xs text-slate-500">
          Scholr doesn&apos;t write exam answers for you in this subject. Try the questions below; after marking
          you&apos;ll see what the examiners said.
        </p>
      )}
      {data.worked && data.examiner && <ExaminerInsightsView data={data.examiner} />}
    </div>
  );
}
