"use client";

import Link from "next/link";
import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Chip } from "@/components/ui";
import type { Lesson } from "@/lib/api";
import { Sources } from "./Sources";

// A worked example, one step at a time (docs/STUDENT-APP.md AC-U13). Six lines of algebra at once are read
// past, not worked through; a step she asks for is a step she has thought about first. Nothing is hidden that
// she cannot see with one tap, and the whole example opens at once for revision or for printing.
const LEVELS = { basic: "Basic", standard: "Standard", exam: "Exam level" } as const;

export function WorkedExample({
  example,
  index,
  askHref,
}: {
  example: Lesson["worked_examples"][number];
  index: number;
  askHref: ((q: string) => string) | null;
}) {
  const [shown, setShown] = useState(0);
  const total = example.steps.length;
  const allShown = shown >= total;

  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-fun font-bold text-emerald-900">Worked example {index + 1}</h3>
        <div className="flex items-center gap-2">
          {example.level && <Chip tone={example.level === "exam" ? "brand" : "neutral"}>{LEVELS[example.level]}</Chip>}
          {example.checked === "sympy" && <Chip tone="good">Answer checked by SymPy</Chip>}
          {total > 1 && !allShown && (
            <button
              onClick={() => setShown(total)}
              className="text-[11px] font-semibold text-emerald-800 hover:underline"
            >
              Show all steps
            </button>
          )}
        </div>
      </div>

      <MathText text={example.problem} className="text-sm font-medium text-slate-900" />

      {total > 0 && (
        <>
          {shown === 0 && (
            <div className="rounded-xl border border-dashed border-emerald-300 bg-white/80 p-3 text-xs text-slate-700">
              <span className="font-bold text-emerald-900">🤔 Pause &amp; Predict:</span> Before revealing the working, what would be your first move? What formula, identity, or rearrangement will you use?
            </div>
          )}

          <ol className="ml-5 list-decimal space-y-1 text-sm text-slate-700">
            {example.steps.slice(0, shown).map((step, j) => (
              <li key={j}>
                <MathText text={step} />
              </li>
            ))}
          </ol>
          {!allShown && (
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => setShown(shown + 1)}
                className="rounded-xl border border-emerald-300 bg-white px-3 py-1.5 text-xs font-fun font-bold text-emerald-800 hover:bg-emerald-50"
              >
                {shown === 0 ? "Ready? Show step 1" : `Show step ${shown + 1}`}
              </button>
              <span className="text-[11px] text-slate-500">
                {total - shown} of {total} steps still hidden
              </span>
            </div>
          )}
        </>
      )}

      {allShown && (
        <>
          <div className="text-sm font-semibold text-slate-900">
            Answer: <MathText text={example.final_answer} />
            {example.unit ? ` ${example.unit}` : null}
          </div>

          <div className="mt-1 flex flex-col gap-1.5 rounded-xl border border-emerald-200 bg-emerald-100/60 p-3 text-xs text-slate-800">
            <div className="flex items-center justify-between">
              <span className="font-fun font-bold text-emerald-900">🎯 Now Try One Like This:</span>
              <span className="text-[10px] text-emerald-700 font-semibold">Transfer Practice</span>
            </div>
            <p className="text-slate-700">
              You&apos;ve seen the method worked out. Now prove you own it by solving a question in <strong>Check Yourself</strong> below with fresh numbers!
            </p>
            <a
              href="#part-check"
              className="self-start inline-flex items-center gap-1 rounded-lg bg-emerald-700 px-2.5 py-1 text-[11px] font-bold text-white shadow-2xs hover:bg-emerald-800 transition"
            >
              <span>↓ Jump to Check Yourself</span>
            </a>
          </div>
        </>
      )}

      <Sources sources={example.sources} />
      {askHref && (
        <Link
          href={askHref(example.problem)}
          className="self-start text-xs font-fun font-bold text-orange-600 hover:underline"
        >
          🦉 Don&apos;t follow a step? Ask the Tutor
        </Link>
      )}
    </div>
  );
}
