"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import type { Lesson } from "@/lib/api";

// The lesson's own two-voice dialogue (lesson.podcast_script, written with the lesson from her books), shown one
// exchange at a time so she thinks about each question before reading the answer. It holds nothing beyond what
// the lesson already contains; topics without a script show nothing.
export function ConceptDialogue({ script }: { script: NonNullable<Lesson["podcast_script"]> }) {
  const [shown, setShown] = useState(Math.min(2, script.length));
  if (script.length === 0) return null;
  const allShown = shown >= script.length;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 md:p-5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900">💬 Talk it through</h3>
          <p className="text-xs text-slate-500">
            The questions a student would ask about this topic, answered one at a time.
          </p>
        </div>
        {!allShown && (
          <button
            type="button"
            onClick={() => setShown(script.length)}
            className="text-xs font-bold text-blue-600 hover:underline cursor-pointer"
          >
            Show all {script.length}
          </button>
        )}
      </div>

      <div className="space-y-2.5 max-w-3xl">
        {script.slice(0, shown).map((turn, i) => {
          const asker = i % 2 === 0;
          return (
            <div
              key={i}
              className={`flex items-start gap-3 rounded-xl border p-3 ${
                asker ? "border-slate-200 bg-slate-50 mr-8" : "border-blue-200 bg-blue-50/60 ml-8"
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-extrabold text-white ${
                  asker ? "bg-slate-700" : "bg-blue-700"
                }`}
              >
                {turn.speaker.slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0">
                <div className="text-xs font-bold text-slate-900">{turn.speaker}</div>
                <MathText text={turn.text} className="text-sm leading-relaxed text-slate-800" />
              </div>
            </div>
          );
        })}
      </div>

      {!allShown && (
        <button
          type="button"
          onClick={() => setShown((s) => Math.min(script.length, s + 2))}
          className="w-full rounded-xl border border-dashed border-blue-300 py-2 text-xs font-bold text-blue-700 hover:bg-blue-50 cursor-pointer"
        >
          Next question ↓ ({script.length - shown} left)
        </button>
      )}
    </div>
  );
}
