"use client";

import Link from "next/link";
import { useState } from "react";
import type { ItemCard, Question } from "@/lib/api";
import { getCommandWordInfo } from "@/lib/commandWords";
import { useApi } from "@/lib/useApi";
import { AnswerBox } from "../AnswerBox";
import { MathText } from "../MathText";
import { Button, ErrorNote } from "../ui";

// One bank question, opened in place on a topic page: read it, answer it, get it marked, ask about it.
export function TryQuestion({
  item,
  askHref,
  label: labelOverride,
  startOpen = false,
  onAnswered,
}: {
  item: ItemCard;
  // The question's own subject is passed too: a warm-up on an IIT lesson asks about an IGCSE question.
  askHref: (question: string, subjectId: string) => string;
  label?: string;
  startOpen?: boolean;
  onAnswered?: () => void;
}) {
  const [open, setOpen] = useState(startOpen);
  const [showCmdTip, setShowCmdTip] = useState(false);
  const question = useApi<Question>(open ? `/questions/${item.id}` : null);
  const label = labelOverride ?? item.label;

  const targetMins = Math.max(1, Math.round(item.marks * 1.2));
  const cmdInfo = getCommandWordInfo(item.command_word);

  const contextText = question.data?.context ?? item.context;
  const stemText = question.data?.stem ?? item.stem;

  return (
    <div className="rounded-2xl border border-amber-200/80 bg-white p-3.5 shadow-2xs transition">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold text-slate-600">
          <span>{label} · {item.marks} mark{item.marks === 1 ? "" : "s"}</span>
          <span
            className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600"
            title="Cambridge Extended pacing target (~1.2 min per mark)"
          >
            ⏱ ~{targetMins} min
          </span>
          {item.command_word && (
            <button
              onClick={() => setShowCmdTip(!showCmdTip)}
              className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200 hover:bg-amber-100 transition"
              title="Click to view Cambridge examiner expectations for this command word"
            >
              <span>🎯 {item.command_word}</span>
              <span className="text-[9px] text-amber-600 font-normal">info</span>
            </button>
          )}
        </div>
        <Button
          variant={open ? "ghost" : "secondary"}
          className="h-8 px-3 text-xs rounded-xl font-medium"
          onClick={() => setOpen(!open)}
        >
          {open ? "Collapse ▲" : "Solve ✍️"}
        </Button>
      </div>

      {showCmdTip && cmdInfo && (
        <div className="mt-2.5 rounded-xl border border-amber-300 bg-amber-50/90 p-2.5 text-xs text-amber-950">
          <div className="flex items-center justify-between">
            <span className="font-bold font-fun text-amber-900">
              Examiner Expectation: &ldquo;{item.command_word}&rdquo;
            </span>
            <button onClick={() => setShowCmdTip(false)} className="text-[10px] text-amber-700 hover:underline">
              ✕
            </button>
          </div>
          <p className="mt-0.5 text-slate-700">{cmdInfo.meaning}</p>
          <p className="mt-1 font-medium text-amber-900">💡 Tip: {cmdInfo.examinerTip}</p>
        </div>
      )}

      {/* Question context & stem: ALWAYS displayed so the student immediately sees what is asked */}
      {(stemText || contextText) && (
        <div className="mt-2.5 flex flex-col gap-1.5 text-slate-800">
          {contextText && (
            <div className="rounded-lg bg-slate-50 p-2 text-xs text-slate-600 border border-slate-100">
              <MathText text={contextText} />
            </div>
          )}
          {stemText && (
            <div className="text-sm font-medium text-slate-900 leading-relaxed">
              <MathText text={stemText} />
            </div>
          )}
        </div>
      )}

      {open && question.error ? <div className="mt-2"><ErrorNote error={question.error} /></div> : null}

      {open && question.loading && !question.data && (
        <div className="mt-3 flex items-center gap-2 text-xs text-amber-700">
          <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-amber-600 border-t-transparent" />
          <span>Opening answer space...</span>
        </div>
      )}

      {open && question.data && (
        <div className="mt-3 flex flex-col gap-3 pt-2 border-t border-slate-100">
          <AnswerBox question={question.data} onAnswered={() => onAnswered?.()} />
          <div className="flex items-center justify-between pt-1">
            <Link
              href={askHref(question.data.stem, question.data.subject_id)}
              className="self-start text-xs font-fun font-bold text-orange-600 hover:underline"
            >
              🦉 Ask the Tutor about this question
            </Link>
            <button
              onClick={() => setOpen(false)}
              className="text-xs text-slate-400 hover:text-slate-600 transition"
            >
              Hide answer box ▲
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
