"use client";

import { useState } from "react";
import type { CommandWords, Question } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// What the question's command word asks for, in Cambridge's own definition from the subject config (checked source
// named underneath). Nothing is shown for a subject or a command word the checked source does not cover: this never
// guesses how a question is marked — the mark scheme and the examiner's comments come with her feedback.
export function CommandWordRubric({ question }: { question: Question }) {
  const [open, setOpen] = useState(false);
  const tested = question.skill_ids ?? [];
  const words = useApi<CommandWords>(
    question.command_word || tested.length ? `/subjects/${question.subject_id}/command-words` : null,
  );
  const word = question.command_word?.trim().toLowerCase() ?? "";
  const definition = words.data?.definitions[word];
  // Which assessment objectives this question tests (improvement 6), so she writes for all of them.
  const skills = (words.data?.skills ?? []).filter((x) => tested.includes(x.id));
  const aos =
    skills.length > 0 ? (
      <span
        className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-0.5 text-[11px] font-fun font-bold text-slate-700"
        title={skills.map((x) => `${x.code}: ${x.name}`).join("\n")}
      >
        Tests {skills.map((x) => x.code).join(" · ")}
      </span>
    ) : null;
  if (!definition) return aos;

  return (
    <span className="relative inline-flex items-center gap-1.5">
      {aos}
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-0.5 text-[11px] font-fun font-bold text-purple-800 hover:bg-purple-100"
        aria-expanded={open}
      >
        What &ldquo;{word}&rdquo; asks for {open ? "▲" : "▼"}
      </button>
      {open && (
        <span className="absolute left-0 top-full z-30 mt-2 block w-72 rounded-2xl border border-slate-200 bg-white p-3 text-left text-xs font-medium normal-case tracking-normal text-slate-700 shadow-xl">
          <span className="block font-bold text-slate-900">{definition}.</span>
          <span className="mt-1.5 block text-[10px] text-slate-500">{words.data?.source}</span>
        </span>
      )}
    </span>
  );
}
