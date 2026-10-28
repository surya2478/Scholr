"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip } from "@/components/ui";
import type { Lesson } from "@/lib/api";

function normalizeAnswer(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/\$/g, "")
    .replace(/\s+/g, "")
    .replace(/^x=/, "")
    .replace(/^y=/, "");
}

export function ActiveRecallDeck({ lesson }: { lesson: Lesson }) {
  const terms = lesson.key_terms ?? [];
  const examples = lesson.worked_examples ?? [];
  const examAnswers = lesson.exam_answers ?? [];

  const hasTerms = terms.length > 0;
  const hasExamples = examples.length > 0;
  const hasExamAnswers = examAnswers.length > 0;

  const defaultTab = hasTerms ? "flashcards" : hasExamples ? "try-example" : "exam-points";
  const [tab, setTab] = useState<"flashcards" | "try-example" | "exam-points">(defaultTab);

  // Flashcard state
  const [cardIndex, setCardIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [masteredTerms, setMasteredTerms] = useState<Set<number>>(new Set());

  // Worked example self-test state
  const [exIndex, setExIndex] = useState(0);
  const [userAttempt, setUserAttempt] = useState("");
  const [checkResult, setCheckResult] = useState<"idle" | "correct" | "not_quite">("idle");
  const [showHint, setShowHint] = useState(false);
  const [showSolution, setShowSolution] = useState(false);

  // Exam answer checklist state
  const [eaIndex, setEaIndex] = useState(0);
  const [eaRevealed, setEaRevealed] = useState(false);
  const [checkedPoints, setCheckedPoints] = useState<Set<number>>(new Set());

  if (!hasTerms && !hasExamples && !hasExamAnswers) {
    return null;
  }

  const currentTerm = terms[cardIndex] ?? terms[0];
  const currentEx = examples[exIndex] ?? examples[0];
  const currentEa = examAnswers[eaIndex] ?? examAnswers[0];

  function handleCheckExample(e: React.FormEvent) {
    e.preventDefault();
    if (!currentEx || !userAttempt.trim()) return;
    const expected = normalizeAnswer(currentEx.final_answer);
    const actual = normalizeAnswer(userAttempt);
    const expectedWithUnit = currentEx.unit
      ? normalizeAnswer(`${currentEx.final_answer}${currentEx.unit}`)
      : expected;
    if (actual === expected || actual === expectedWithUnit) {
      setCheckResult("correct");
      setShowSolution(true);
    } else {
      setCheckResult("not_quite");
    }
  }

  function selectExample(idx: number) {
    setExIndex(idx);
    setUserAttempt("");
    setCheckResult("idle");
    setShowHint(false);
    setShowSolution(false);
  }

  return (
    <Card
      title="🧠 Active Recall & Quick Self-Check"
      subtitle="Test your memory on key definitions, worked problems, and mark-scheme points before moving on"
      tone="emerald"
    >
      <div className="space-y-4">
        {/* Mode Switcher */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-emerald-100 pb-3">
          <div className="flex flex-wrap items-center gap-1.5 rounded-2xl bg-emerald-100/70 p-1">
            {hasTerms && (
              <button
                type="button"
                onClick={() => setTab("flashcards")}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-fun font-bold transition cursor-pointer ${
                  tab === "flashcards"
                    ? "bg-white text-emerald-950 shadow-2xs"
                    : "text-emerald-800 hover:text-emerald-950"
                }`}
              >
                🃏 Term Flashcards ({masteredTerms.size}/{terms.length})
              </button>
            )}
            {hasExamples && (
              <button
                type="button"
                onClick={() => setTab("try-example")}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-fun font-bold transition cursor-pointer ${
                  tab === "try-example"
                    ? "bg-white text-emerald-950 shadow-2xs"
                    : "text-emerald-800 hover:text-emerald-950"
                }`}
              >
                ⚡ Beat the Worked Example ({examples.length})
              </button>
            )}
            {hasExamAnswers && (
              <button
                type="button"
                onClick={() => setTab("exam-points")}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-fun font-bold transition cursor-pointer ${
                  tab === "exam-points"
                    ? "bg-white text-emerald-950 shadow-2xs"
                    : "text-emerald-800 hover:text-emerald-950"
                }`}
              >
                🎯 Mark-Scheme Drill ({examAnswers.length})
              </button>
            )}
          </div>

          {tab === "flashcards" && terms.length > 0 && (
            <span className="text-xs font-semibold text-emerald-800">
              Card {cardIndex + 1} of {terms.length}
            </span>
          )}
        </div>

        {/* TAB 1: FLASHCARDS */}
        {tab === "flashcards" && currentTerm && (
          <div className="space-y-3">
            <div
              onClick={() => setFlipped((f) => !f)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setFlipped((f) => !f);
                }
              }}
              className={`group relative flex min-h-[160px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 p-6 text-center transition-all select-none ${
                flipped
                  ? "border-emerald-300 bg-gradient-to-br from-emerald-50/90 via-white to-teal-50/70 shadow-sm"
                  : "border-slate-200 bg-white hover:border-emerald-300 shadow-2xs"
              }`}
            >
              <div className="absolute top-3 left-3 flex items-center gap-1.5">
                <Chip tone={flipped ? "good" : "neutral"}>
                  {flipped ? "Cambridge Definition" : "Key Term"}
                </Chip>
                {masteredTerms.has(cardIndex) && <Chip tone="good">✓ Mastered</Chip>}
              </div>
              <span className="absolute top-3 right-3 text-[11px] font-semibold text-slate-400 group-hover:text-emerald-700">
                {flipped ? "Tap to show term ↺" : "Tap to flip ↻"}
              </span>

              {!flipped ? (
                <div className="space-y-2 py-4">
                  <div className="text-lg md:text-xl font-fun font-bold text-slate-900">
                    <MathText text={currentTerm.term} />
                  </div>
                  <p className="text-xs text-slate-500">
                    Recall the exact definition in your head, then tap to verify.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 py-4 max-w-xl">
                  <div className="text-xs font-bold uppercase tracking-wider text-emerald-700">
                    <MathText text={currentTerm.term} />
                  </div>
                  <div className="text-sm md:text-base font-medium text-slate-800 leading-relaxed">
                    <MathText text={currentTerm.meaning} />
                  </div>
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="h-9 px-3 text-xs"
                  disabled={cardIndex === 0}
                  onClick={() => {
                    setCardIndex((i) => Math.max(0, i - 1));
                    setFlipped(false);
                  }}
                >
                  ← Previous
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="h-9 px-3 text-xs"
                  disabled={cardIndex >= terms.length - 1}
                  onClick={() => {
                    setCardIndex((i) => Math.min(terms.length - 1, i + 1));
                    setFlipped(false);
                  }}
                >
                  Next →
                </Button>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const next = new Set(masteredTerms);
                    next.delete(cardIndex);
                    setMasteredTerms(next);
                    setFlipped(false);
                    if (cardIndex < terms.length - 1) setCardIndex(cardIndex + 1);
                  }}
                  className="rounded-xl border border-slate-200 bg-amber-50 px-3 py-1.5 text-xs font-fun font-bold text-amber-800 hover:bg-amber-100 cursor-pointer"
                >
                  ↻ Review again
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const next = new Set(masteredTerms);
                    next.add(cardIndex);
                    setMasteredTerms(next);
                    setFlipped(false);
                    if (cardIndex < terms.length - 1) setCardIndex(cardIndex + 1);
                  }}
                  className="rounded-xl bg-emerald-600 px-3.5 py-1.5 text-xs font-fun font-bold text-white shadow-2xs hover:bg-emerald-700 cursor-pointer"
                >
                  ✓ Got it
                </button>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: BEAT THE WORKED EXAMPLE */}
        {tab === "try-example" && currentEx && (
          <div className="space-y-3">
            {examples.length > 1 && (
              <div className="flex flex-wrap items-center gap-1.5">
                {examples.map((ex, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => selectExample(idx)}
                    className={`rounded-xl px-3 py-1 text-xs font-fun font-bold transition cursor-pointer ${
                      exIndex === idx
                        ? "bg-emerald-600 text-white shadow-2xs"
                        : "border border-emerald-200 bg-white text-slate-700 hover:bg-emerald-50"
                    }`}
                  >
                    Problem {idx + 1}
                    {ex.level ? ` (${ex.level})` : ""}
                  </button>
                ))}
              </div>
            )}

            <div className="rounded-2xl border border-emerald-200 bg-white p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-fun font-bold uppercase tracking-wider text-emerald-800">
                  Solve Before Peeking
                </span>
                <div className="flex items-center gap-1.5">
                  {currentEx.level && <Chip tone="brand">{currentEx.level}</Chip>}
                  {currentEx.checked === "sympy" && <Chip tone="good">SymPy Verified</Chip>}
                </div>
              </div>

              <div className="text-sm font-medium text-slate-900 leading-relaxed">
                <MathText text={currentEx.problem} />
              </div>

              {showHint && currentEx.strategy && (
                <div className="rounded-xl border border-blue-200 bg-blue-50/80 p-3 text-xs text-slate-800">
                  <span className="font-bold text-blue-900">💡 Strategy Hint: </span>
                  <MathText text={currentEx.strategy} />
                </div>
              )}

              <form onSubmit={handleCheckExample} className="flex flex-wrap items-center gap-2 pt-1">
                <input
                  type="text"
                  value={userAttempt}
                  onChange={(e) => {
                    setUserAttempt(e.target.value);
                    if (checkResult !== "idle") setCheckResult("idle");
                  }}
                  placeholder={
                    currentEx.unit
                      ? `Your numerical answer (in ${currentEx.unit})…`
                      : "Type your final answer…"
                  }
                  className="h-10 min-w-[200px] flex-1 rounded-xl border border-slate-200 bg-slate-50/70 px-3.5 text-sm font-medium text-slate-900 outline-none focus:border-emerald-500 focus:bg-white"
                />
                {currentEx.unit && (
                  <span className="rounded-lg bg-slate-100 px-2.5 py-2 text-xs font-bold text-slate-700">
                    {currentEx.unit}
                  </span>
                )}
                <Button type="submit" className="h-10 px-4 text-xs">
                  Check Answer
                </Button>
                {currentEx.strategy && !showHint && (
                  <button
                    type="button"
                    onClick={() => setShowHint(true)}
                    className="rounded-xl border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-fun font-bold text-blue-800 hover:bg-blue-100 cursor-pointer"
                  >
                    💡 Hint
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setShowSolution((s) => !s)}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  {showSolution ? "Hide solution" : "Reveal full steps"}
                </button>
              </form>

              {checkResult === "correct" && (
                <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-3 text-xs font-semibold text-emerald-900">
                  🎉 Spot on! Your answer matches the verified solution:{" "}
                  <MathText text={currentEx.final_answer} className="font-bold" />
                  {currentEx.unit ? ` ${currentEx.unit}` : ""}
                </div>
              )}

              {checkResult === "not_quite" && (
                <div className="rounded-xl border border-amber-300 bg-amber-50 p-3 text-xs text-amber-950">
                  <span className="font-bold">Not quite matching yet.</span> Check your units, signs, or rounding—or click{" "}
                  <button
                    type="button"
                    onClick={() => setShowSolution(true)}
                    className="font-bold underline cursor-pointer"
                  >
                    Reveal full steps
                  </button>{" "}
                  to compare your working line by line.
                </div>
              )}

              {showSolution && (
                <div className="mt-2 space-y-2 rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs">
                  <div className="font-fun font-bold text-slate-800">Step-by-Step Working:</div>
                  <ol className="ml-4 list-decimal space-y-1 text-slate-700">
                    {currentEx.steps.map((st, i) => (
                      <li key={i}>
                        <MathText text={st} />
                      </li>
                    ))}
                  </ol>
                  <div className="pt-1 font-bold text-emerald-900">
                    Final Answer: <MathText text={currentEx.final_answer} />
                    {currentEx.unit ? ` ${currentEx.unit}` : ""}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: MARK-SCHEME DRILL */}
        {tab === "exam-points" && currentEa && (
          <div className="space-y-3">
            {examAnswers.length > 1 && (
              <div className="flex flex-wrap gap-1.5">
                {examAnswers.map((_, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setEaIndex(idx);
                      setEaRevealed(false);
                      setCheckedPoints(new Set());
                    }}
                    className={`rounded-xl px-3 py-1 text-xs font-fun font-bold transition cursor-pointer ${
                      eaIndex === idx
                        ? "bg-emerald-600 text-white"
                        : "border border-emerald-200 bg-white text-slate-700 hover:bg-emerald-50"
                    }`}
                  >
                    Question {idx + 1}
                  </button>
                ))}
              </div>
            )}

            <div className="rounded-2xl border border-emerald-200 bg-white p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-fun font-bold uppercase tracking-wider text-indigo-800">
                  Typical Exam Question ({currentEa.points.length} marks)
                </span>
                <Chip tone="brand">1 point per mark</Chip>
              </div>
              <div className="text-sm font-semibold text-slate-900">
                <MathText text={currentEa.question} />
              </div>

              {!eaRevealed ? (
                <div className="space-y-2 pt-1">
                  <p className="text-xs text-slate-600">
                    Think of <strong>{currentEa.points.length} distinct points</strong> an examiner would credit, then reveal the mark scheme to score yourself.
                  </p>
                  <Button type="button" onClick={() => setEaRevealed(true)} className="h-9 px-4 text-xs">
                    Reveal Mark-Scheme Points
                  </Button>
                </div>
              ) : (
                <div className="space-y-2 pt-1">
                  <p className="text-xs font-semibold text-emerald-900">
                    Tick each mark-scheme point you included in your mental answer:
                  </p>
                  <ul className="space-y-1.5">
                    {currentEa.points.map((pt, idx) => {
                      const ticked = checkedPoints.has(idx);
                      return (
                        <li key={idx}>
                          <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-slate-200 bg-slate-50/70 p-2.5 text-xs hover:bg-emerald-50/50">
                            <input
                              type="checkbox"
                              checked={ticked}
                              onChange={() => {
                                const next = new Set(checkedPoints);
                                if (ticked) next.delete(idx);
                                else next.add(idx);
                                setCheckedPoints(next);
                              }}
                              className="mt-0.5 rounded accent-emerald-600"
                            />
                            <span className="flex-1 text-slate-800">
                              <MathText text={pt} />
                            </span>
                            <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                              [1]
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                  <div className="text-xs font-bold text-slate-700 pt-1">
                    Self-score: {checkedPoints.size} / {currentEa.points.length} marks
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
