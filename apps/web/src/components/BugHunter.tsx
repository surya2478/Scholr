"use client";

import { useState } from "react";
import { ExaminerInsightsView } from "@/components/ExaminerInsights";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type BugChallenge, type BugVerificationOut } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// Bug Hunter: a candidate's working on a real past-paper question, with one slip in it. She finds the step, names the
// kind of error, and decides whether that step's mark would still be awarded. Every challenge is built from a solved
// question a parent approved, with the slip checked by SymPy (mistakes/challenges.py) — nothing here is invented.

const BUG_TYPES = [
  { value: "calculation", label: "Calculation slip" },
  { value: "conceptual", label: "Wrong method or idea" },
  { value: "misreading", label: "Misread the question" },
  { value: "accuracy", label: "Rounded too early" },
];

export function BugHunter() {
  const challenges = useApi<BugChallenge[]>("/mistakes/challenges");
  const [active, setActive] = useState<BugChallenge | null>(null);
  const [step, setStep] = useState<number | null>(null);
  const [bugType, setBugType] = useState("calculation");
  const [keepsMark, setKeepsMark] = useState<boolean | null>(null);
  const [verdict, setVerdict] = useState<BugVerificationOut | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  function open(c: BugChallenge) {
    setActive(c);
    setStep(null);
    setKeepsMark(null);
    setVerdict(null);
    setError(null);
  }

  async function submit() {
    if (!active || step === null || keepsMark === null) return;
    setBusy(true);
    setError(null);
    try {
      setVerdict(
        await api<BugVerificationOut>(`/mistakes/challenges/${active.id}/verify`, {
          method: "POST",
          json: { selected_step: step, selected_bug_type: bugType, award_method_mark: keepsMark },
        })
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="🔬 Bug Hunter"
      subtitle="A candidate's working on a real exam question has one slip in it. Find it, and decide what it costs."
      tone="amber"
    >
      {error ? <ErrorNote error={error} /> : null}
      {challenges.error ? <ErrorNote error={challenges.error} /> : null}

      {!active && (
        <div className="flex flex-col gap-2">
          {challenges.data?.length === 0 && (
            <Empty>No challenges yet — they are built from solved exam questions once a parent approves them.</Empty>
          )}
          {challenges.data?.map((c) => (
            <button
              key={c.id}
              onClick={() => open(c)}
              className="flex flex-col items-start rounded-2xl border border-amber-200 bg-white px-3.5 py-2.5 text-left hover:bg-amber-50"
            >
              <span className="text-sm font-semibold text-slate-900">{c.title}</span>
              <span className="text-[11px] text-slate-500">
                {c.label} · {c.marks_available} marks · {c.student_steps.length} steps
              </span>
            </button>
          ))}
        </div>
      )}

      {active && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Chip tone="neutral">
              {active.label} · {active.marks_available} marks
            </Chip>
            <button onClick={() => setActive(null)} className="text-[11px] font-semibold text-amber-800 hover:underline">
              Choose another
            </button>
          </div>
          {active.question_context && <MathText text={active.question_context} className="text-sm text-slate-700" />}
          <MathText text={active.question_stem} className="text-sm font-medium text-slate-900" />

          <p className="text-xs font-bold text-slate-600">The candidate&apos;s working — tap the step with the slip:</p>
          <ol className="flex flex-col gap-1.5">
            {active.student_steps.map((s) => (
              <li key={s.step_number}>
                <button
                  onClick={() => !verdict && setStep(s.step_number)}
                  className={`flex w-full items-start gap-2 rounded-xl border px-3 py-2 text-left text-sm ${
                    verdict && s.step_number === verdict.bug_step
                      ? "border-rose-300 bg-rose-50"
                      : step === s.step_number
                        ? "border-amber-400 bg-amber-50"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <span className="font-bold text-slate-500">{s.step_number}.</span>
                  <MathText text={s.text} className="flex-1" />
                </button>
              </li>
            ))}
          </ol>
          <p className="text-sm text-slate-800">
            Answer given: <MathText text={active.final_answer} />
          </p>

          {!verdict && (
            <div className="flex flex-col gap-2 rounded-2xl border border-amber-200 bg-amber-50/50 p-3">
              <label className="text-xs font-bold text-slate-700">
                What kind of error is it?{" "}
                <select
                  value={bugType}
                  onChange={(e) => setBugType(e.target.value)}
                  className="ml-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs"
                >
                  {BUG_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-slate-700">
                Does that step still earn its mark?
                {[
                  { value: true, label: "Yes, it keeps it" },
                  { value: false, label: "No, it's lost" },
                ].map((o) => (
                  <button
                    key={String(o.value)}
                    onClick={() => setKeepsMark(o.value)}
                    className={`rounded-lg border px-2.5 py-1 ${
                      keepsMark === o.value ? "border-amber-500 bg-white" : "border-slate-200 bg-white/60"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
              <Button
                onClick={() => void submit()}
                disabled={busy || step === null || keepsMark === null}
                className="h-8 self-start px-3 text-xs"
              >
                {busy ? "Checking…" : "Give my verdict"}
              </Button>
            </div>
          )}

          {verdict && (
            <div className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-3 text-sm">
              <p className="text-[11px] font-semibold">
                {verdict.correct_step ? "✓" : "✗"} the step · {verdict.correct_type ? "✓" : "✗"} kind of error ·{" "}
                {verdict.correct_mark ? "✓" : "✗"} the mark
              </p>
              <p className="text-slate-800">{verdict.bug_explanation}</p>
              <p className="text-slate-700">
                It should read: <MathText text={verdict.correct_text} />
              </p>
              <p className="text-slate-700">{verdict.examiner_report}</p>
              <p className="text-xs font-semibold text-slate-500">{verdict.official_mark}</p>
              {verdict.examiner && <ExaminerInsightsView data={verdict.examiner} />}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
