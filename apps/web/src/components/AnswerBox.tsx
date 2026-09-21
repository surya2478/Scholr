"use client";

import Link from "next/link";
import { useState } from "react";
import { api, ApiError, type Attempt, type Evaluation, type Question } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useMe } from "./AppShell";
import { EvaluationCard } from "./EvaluationCard";
import { MathField } from "./MathField";
import { MathText } from "./MathText";
import { PhotoAnswer } from "./PhotoAnswer";
import { Button, ErrorNote } from "./ui";

// One question: pre-answer confidence (AC-L4), typed working + final answer, then marking (unless a study test).
// Subjects whose config sets answer_input "expression" get the MathLive maths keyboard; answers are sent as $LaTeX$.
export function AnswerBox({
  question,
  sessionId,
  assessmentId,
  markNow = true,
  onAnswered,
}: {
  question: Question;
  sessionId?: string;
  assessmentId?: string;
  markNow?: boolean;
  onAnswered?: (attempt: Attempt, evaluation: Evaluation | null) => void;
}) {
  const me = useMe();
  const enrollments = me?.student?.enrollments ?? [];
  const maths = enrollments.find((e) => e.subject_id === question.subject_id)?.answer_input === "expression";
  const [confidence, setConfidence] = useState<number | null>(null);
  const [working, setWorking] = useState("");
  const [line, setLine] = useState("");
  const [finalAnswer, setFinal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [mode, setMode] = useState<"typed" | "photo">("typed");

  function addLine() {
    if (!line.trim()) return;
    setWorking((w) => `${w}${w && !w.endsWith("\n") ? "\n" : ""}$${line}$\n`);
    setLine("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const answer = finalAnswer.trim();
    try {
      const attempt = await api<Attempt>("/attempts", {
        method: "POST",
        json: {
          question_item_id: question.id,
          idempotency_key: crypto.randomUUID(),
          working: working || null,
          final_answer: answer ? (maths ? `$${answer}$` : answer) : null,
          pre_confidence: confidence,
          session_id: sessionId ?? null,
          assessment_id: assessmentId ?? null,
        },
      });
      setSubmitted(true);
      let result: Evaluation | null = null;
      if (markNow) {
        try {
          result = await api<Evaluation>(`/attempts/${attempt.id}/evaluate`, { method: "POST" });
          setEvaluation(result);
        } catch (err) {
          setError(err instanceof ApiError && err.status === 503 ? new Error("Marking is unavailable right now — your answer is saved.") : err);
        }
      }
      onAnswered?.(attempt, result);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Friendly Question Stem Box */}
      <div className="rounded-3xl border-2 border-orange-200/90 bg-[#FFFAF5] p-5 md:p-6 shadow-2xs space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-500 border-b border-orange-100 pb-2.5">
          <span className="font-fun font-bold uppercase tracking-wider text-orange-700">
            Challenge Question
          </span>
          <span className="font-fun font-bold text-orange-600 bg-orange-100/90 px-3 py-0.5 rounded-full border border-orange-200">
            {question.marks} Exam Mark{question.marks === 1 ? "" : "s"} ⭐
          </span>
        </div>

        {question.context && (
          <div className="text-xs text-slate-600 leading-relaxed font-medium bg-white/70 p-3 rounded-xl border border-orange-100">
            <MathText text={question.context} />
          </div>
        )}

        <div className="py-2 text-base md:text-lg text-slate-900 font-medium leading-relaxed">
          <MathText text={question.stem} />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-orange-100/80 text-xs text-slate-500 font-medium">
          <span>
            {question.calculator_allowed === false ? "💡 Non-calculator exam question!" : "✓ Calculator allowed"}
          </span>
          {question.has_diagram && (
            <span className="font-bold text-orange-700 bg-orange-100/80 px-2 py-0.5 rounded-md">
              Original paper has diagram
            </span>
          )}
        </div>
      </div>

      {!submitted && (
        <div className="flex items-center gap-2 text-xs font-semibold bg-amber-50/80 p-1.5 rounded-2xl border border-amber-200/60 w-fit">
          {(["typed", "photo"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={`rounded-xl px-4 py-2 transition-all cursor-pointer font-fun font-bold ${
                mode === m
                  ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-white/60"
              }`}
            >
              {m === "typed" ? "✍️ Type my answer" : "📸 Photo of my working"}
            </button>
          ))}
        </div>
      )}

      {!submitted && mode === "photo" && (
        <PhotoAnswer
          question={question}
          sessionId={sessionId}
          assessmentId={assessmentId}
          markNow={markNow}
          onAnswered={() => onAnswered?.({ id: "", status: "photo", evaluation_id: null }, null)}
        />
      )}

      {!submitted && mode === "typed" && (
        <form onSubmit={submit} className="flex flex-col gap-4">
          {/* Confidence Selector */}
          <fieldset className="flex flex-col gap-2 rounded-2xl border border-amber-200/70 bg-[#FFFDF9] p-4 text-xs">
            <legend className="font-fun font-bold text-slate-800 text-xs px-1">
              How confident do you feel before solving this?
            </legend>
            <div className="flex flex-wrap gap-2 pt-1">
              {[
                { label: "Not sure", emoji: "🤔" },
                { label: "A little", emoji: "🙂" },
                { label: "Fairly", emoji: "👍" },
                { label: "Very sure", emoji: "🚀" },
              ].map((item, i) => (
                <button
                  type="button"
                  key={item.label}
                  onClick={() => setConfidence(i + 1)}
                  className={`flex items-center gap-1.5 rounded-xl border px-3.5 py-1.5 font-fun font-bold transition-all cursor-pointer ${
                    confidence === i + 1
                      ? "border-orange-400 bg-orange-100 text-orange-800 shadow-2xs scale-105"
                      : "border-amber-200 bg-white text-slate-600 hover:bg-amber-50"
                  }`}
                >
                  <span>{item.emoji}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          </fieldset>

          {/* Working Textarea */}
          <label className="flex flex-col gap-1.5 text-xs font-fun font-bold text-slate-800">
            Show your step-by-step method / working:
            <textarea
              value={working}
              onChange={(e) => setWorking(e.target.value)}
              rows={4}
              className="rounded-2xl border-2 border-amber-200 bg-white p-3.5 font-mono text-sm font-normal text-slate-800 focus:border-orange-400 outline-none transition-colors"
              placeholder={
                maths
                  ? "Show your steps here. Build a math line below and tap 'Add to working', or type directly."
                  : "Write your step-by-step reasoning or PEEL argument points here."
              }
            />
          </label>

          {maths && (
            <div className="flex flex-col gap-1.5 text-xs font-fun font-bold text-slate-800 rounded-2xl bg-amber-50/60 border border-amber-200 p-3.5">
              <span>Maths Line Builder (with MathLive keyboard)</span>
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                <MathField value={line} onChange={setLine} label="Maths line for your working" className="flex-1" />
                <Button type="button" variant="secondary" disabled={!line.trim()} onClick={addLine}>
                  Add to working ↵
                </Button>
              </div>
            </div>
          )}

          {working.includes("$") && (
            <div className="rounded-2xl border border-amber-200/80 bg-white p-3.5 text-sm shadow-2xs">
              <span className="text-[11px] font-bold text-slate-400 block mb-1 uppercase tracking-wider">
                Working Preview:
              </span>
              <MathText text={working} />
            </div>
          )}

          {/* Final Answer Input Box */}
          <div className="rounded-2xl border-2 border-amber-300 bg-gradient-to-r from-orange-50 via-amber-50 to-orange-50 p-4 space-y-2">
            <label className="block text-xs font-fun font-bold text-orange-900">
              Final Answer:
            </label>
            {maths ? (
              <MathField value={finalAnswer} onChange={setFinal} label="Final answer" />
            ) : (
              <input
                aria-label="Final answer"
                value={finalAnswer}
                onChange={(e) => setFinal(e.target.value)}
                placeholder="Type your final result or conclusion…"
                className="h-11 w-full rounded-xl border border-amber-300 bg-white px-3.5 text-sm font-normal text-slate-900 outline-none focus:border-orange-500"
              />
            )}
            {maths && (
              <span className="text-[11px] text-slate-500 font-medium block">
                💡 Tip: Type <code className="font-mono bg-white px-1 py-0.5 rounded border border-amber-200">/</code> for fraction and <code className="font-mono bg-white px-1 py-0.5 rounded border border-amber-200">^</code> for power.
              </span>
            )}
          </div>

          <div className="pt-1">
            <Button
              disabled={busy || (!working.trim() && !finalAnswer.trim())}
              className="w-full sm:w-auto"
            >
              {busy ? "Marking with SymPy & Cambridge Rubric…" : markNow ? "Submit & Score Marks! 🎉" : "Save Answer ✓"}
            </Button>
          </div>
        </form>
      )}

      {submitted && !markNow && (
        <div className="rounded-2xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-800 font-medium flex items-center gap-2">
          <span>✓</span>
          <span>Answer saved! It will be evaluated after you finish and submit your test.</span>
        </div>
      )}

      {busy && submitted && (
        <div className="flex items-center gap-2 text-sm text-slate-500 font-medium">
          <span className="animate-spin">🌀</span>
          <span>Checking your steps and mark scheme…</span>
        </div>
      )}

      {error ? <ErrorNote error={error} /> : null}
      {evaluation && <EvaluationCard evaluation={evaluation} />}
      {evaluation && !assessmentId && (
        // Not inside a test: a submitted test is reviewed with the parent, and tutoring is off during one (AC-L5).
        <Link
          href={tutorHref({
            subjectId: question.subject_id,
            objectiveId: question.objective_ids[0],
            ask: `I answered this and want to understand the marking: ${question.stem}`,
          })}
          className="self-start text-xs font-fun font-bold text-orange-600 hover:underline"
        >
          🦉 Ask the Tutor about this answer
        </Link>
      )}
    </div>
  );
}
