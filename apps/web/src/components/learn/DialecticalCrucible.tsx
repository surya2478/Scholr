"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Card, Chip } from "@/components/ui";
import type { Crucible } from "@/lib/api";
import { Sources } from "./Sources";

// The Crucible (learn/crucible.py): the perspectives on a real essay question on this topic, each cited from her
// own coursebook and approved by a parent. It sets out the views and the questions to weigh — it never writes her
// answer or marks it. She answers the question itself below, where it is marked the normal way.

export function DialecticalCrucible({ crucible }: { crucible: Crucible }) {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <Card
      title="⚖️ The Crucible"
      subtitle="The perspectives on a real essay question, from your coursebook — weigh them, then write your own answer"
      tone="purple"
    >
      <div className="flex flex-col gap-3">
        <div className="rounded-2xl border border-purple-200 bg-white p-3">
          <Chip tone="neutral">
            {crucible.question.label} · {crucible.question.marks} marks
          </Chip>
          <MathText text={crucible.stem} className="mt-2 text-sm font-semibold text-slate-900" />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {crucible.perspectives.map((p, i) => (
            <button
              key={i}
              onClick={() => setOpen(open === i ? null : i)}
              className={`rounded-xl border px-3 py-1.5 text-xs font-fun font-bold ${
                open === i ? "border-purple-500 bg-purple-100 text-purple-900" : "border-purple-200 bg-white text-slate-700"
              }`}
            >
              {p.perspective}
              {p.sociologist ? ` · ${p.sociologist}` : ""}
            </button>
          ))}
        </div>

        {open !== null && crucible.perspectives[open] && (
          <div className="flex flex-col gap-1.5 rounded-2xl border border-purple-200 bg-purple-50/40 p-3 text-sm text-slate-800">
            <MathText text={crucible.perspectives[open].argument} />
            {crucible.perspectives[open].key_concept && (
              <p className="text-xs">
                <span className="font-bold">Key idea:</span> {crucible.perspectives[open].key_concept}
              </p>
            )}
            {crucible.perspectives[open].evidence && (
              <p className="text-xs">
                <span className="font-bold">Evidence:</span> {crucible.perspectives[open].evidence}
              </p>
            )}
            <Sources sources={crucible.perspectives[open].sources} />
          </div>
        )}

        {crucible.questions.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-3">
            <p className="text-xs font-bold text-slate-700">Before you write, weigh these:</p>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {crucible.questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}
        <p className="text-[11px] text-slate-500">
          Write your answer to this question in &ldquo;Exam questions&rdquo; below — it is marked there, and you&apos;ll
          see what the examiners said about it afterwards.
        </p>
      </div>
    </Card>
  );
}
