"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type BugChallenge, type BugVerificationOut } from "@/lib/api";
import { useApi } from "@/lib/useApi";

const BUG_CATEGORIES = [
  { value: "conceptual", label: "Conceptual Misunderstanding" },
  { value: "calculation", label: "Calculation / Sign Error" },
  { value: "vocabulary", label: "Vocabulary / Terminology Conflation" },
  { value: "accuracy", label: "Premature Rounding / Accuracy Loss" },
];

export function BugHunter() {
  const [selectedSubject, setSelectedSubject] = useState<string>("");
  const challenges = useApi<BugChallenge[]>(
    `/mistakes/challenges${selectedSubject ? `?subject=${selectedSubject}` : ""}`
  );
  const [activeChallengeId, setActiveChallengeId] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const [selectedBugType, setSelectedBugType] = useState<string>("conceptual");
  const [awardMethodMark, setAwardMethodMark] = useState<boolean>(true);
  const [verdict, setVerdict] = useState<BugVerificationOut | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<unknown>(null);

  const activeChallenge =
    challenges.data?.find((c) => c.id === activeChallengeId) ??
    challenges.data?.[0] ??
    null;

  async function submitVerdict() {
    if (!activeChallenge || selectedStep === null) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api<BugVerificationOut>(
        `/mistakes/challenges/${activeChallenge.id}/verify`,
        {
          method: "POST",
          json: {
            selected_step: selectedStep,
            selected_bug_type: selectedBugType,
            award_method_mark: awardMethodMark,
          },
        }
      );
      setVerdict(result);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function nextCase(id: string) {
    setActiveChallengeId(id);
    setSelectedStep(null);
    setVerdict(null);
    setError(null);
  }

  return (
    <div className="space-y-6">
      {/* Banner */}
      <div className="rounded-3xl border-2 border-orange-200 bg-gradient-to-br from-amber-50 via-[#FFF9F2] to-orange-50 p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center sm:text-left">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
              <span>🕵️‍♀️</span> Chief Examiner Review
            </span>
            <h2 className="text-xl md:text-2xl font-fun font-bold text-slate-900">
              The Cognitive Bug Hunter
            </h2>
            <p className="text-xs md:text-sm text-slate-600 font-medium max-w-xl">
              Inspect synthetic student solutions with real Cambridge and IIT exam traps. Spotting subtle bugs in others&apos; reasoning builds an immune system against making them yourself!
            </p>
          </div>
          <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-2xl text-white shadow-md select-none">
            🔬
          </div>
        </div>

        {/* Subject Filter Pills */}
        <div className="flex flex-wrap gap-2 mt-4 pt-3 border-t border-orange-200/70">
          {[
            { value: "", label: "All Subjects" },
            { value: "math_sciences", label: "📐 Mathematics (0580)" },
            { value: "physical_sciences", label: "⚡ Physics (0625)" },
            { value: "social_sciences", label: "📚 Sociology (0495)" },
          ].map((s) => (
            <button
              key={s.value}
              onClick={() => {
                setSelectedSubject(s.value);
                setVerdict(null);
                setSelectedStep(null);
              }}
              className={`rounded-xl px-3 py-1 text-xs font-fun font-bold transition-all cursor-pointer ${
                selectedSubject === s.value
                  ? "bg-orange-500 text-white shadow-2xs"
                  : "bg-white text-slate-600 hover:bg-orange-100 border border-orange-200"
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {challenges.error ? <ErrorNote error={challenges.error} /> : null}

      {/* Main Challenge Arena */}
      {activeChallenge ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Challenge Selector & Question Stem (4 cols) */}
          <div className="lg:col-span-5 space-y-4">
            <Card
              title="Case Dossier"
              subtitle={`Showing cases for ${selectedSubject || "All Curricula"}`}
            >
              <div className="space-y-2">
                {challenges.data?.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => nextCase(c.id)}
                    className={`w-full text-left p-3 rounded-2xl border transition-all cursor-pointer ${
                      activeChallenge.id === c.id
                        ? "border-orange-400 bg-orange-50/80 shadow-2xs"
                        : "border-slate-200 bg-white hover:border-orange-300 hover:bg-amber-50/30"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs font-fun font-bold">
                      <span className="text-slate-900">{c.title}</span>
                      <Chip tone="neutral">{c.subject_category}</Chip>
                    </div>
                    <div className="text-[11px] text-slate-500 mt-1">
                      {c.topic_name} · {c.marks_available} Marks
                    </div>
                  </button>
                ))}
              </div>
            </Card>

            <Card title="Exam Question Stem" subtitle="Official Cambridge Question">
              <div className="p-3.5 rounded-2xl bg-white border border-slate-200 text-sm font-medium text-slate-900 leading-relaxed">
                <MathText text={activeChallenge.question_stem} />
              </div>
            </Card>
          </div>

          {/* Right Column: Student Solution & Inspector (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <Card
              title={`Examining ${activeChallenge.student_alias}'s Solution`}
              subtitle="Click on the exact line where the reasoning broke down!"
              tone="amber"
            >
              <div className="space-y-3">
                <p className="text-xs text-slate-600 font-medium">
                  Review each step below. Which step contains the fatal algebraic, physical, or sociological flaw?
                </p>

                <div className="space-y-2">
                  {activeChallenge.student_steps.map((step) => (
                    <button
                      key={step.step_number}
                      type="button"
                      onClick={() => {
                        setSelectedStep(step.step_number);
                        setVerdict(null);
                      }}
                      className={`w-full text-left p-3.5 rounded-2xl border-2 transition-all cursor-pointer ${
                        selectedStep === step.step_number
                          ? "border-orange-500 bg-orange-50/90 shadow-sm ring-2 ring-orange-400/30"
                          : "border-slate-200 bg-white hover:border-orange-300 hover:bg-orange-50/30"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs font-fun font-bold text-slate-500 mb-1">
                        <span>Step {step.step_number}</span>
                        {selectedStep === step.step_number && (
                          <span className="text-orange-700 font-bold bg-orange-100 px-2 py-0.5 rounded-full text-[10px]">
                            FLAGGED AS BUG 🎯
                          </span>
                        )}
                      </div>
                      <div className="text-sm font-medium text-slate-800 leading-relaxed">
                        <MathText text={step.text} />
                      </div>
                    </button>
                  ))}
                </div>

                {/* Bug Diagnosis Controls */}
                <div className="pt-3 border-t border-amber-200/70 space-y-3">
                  <div className="space-y-1">
                    <label className="text-xs font-fun font-bold text-slate-800">
                      Misconception Classification:
                    </label>
                    <select
                      value={selectedBugType}
                      onChange={(e) => setSelectedBugType(e.target.value)}
                      className="w-full h-10 rounded-xl border border-amber-300 bg-white px-3 text-xs font-semibold text-slate-800 outline-none focus:border-orange-400"
                    >
                      {BUG_CATEGORIES.map((cat) => (
                        <option key={cat.value} value={cat.value}>
                          {cat.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="awardM"
                      checked={awardMethodMark}
                      onChange={(e) => setAwardMethodMark(e.target.checked)}
                      className="h-4 w-4 rounded text-orange-600 focus:ring-orange-400"
                    />
                    <label htmlFor="awardM" className="text-xs font-medium text-slate-700">
                      Award partial method mark ($M1$) for attempted formula/working
                    </label>
                  </div>

                  <Button
                    disabled={selectedStep === null || busy}
                    onClick={submitVerdict}
                    className="w-full"
                  >
                    {busy ? "Reviewing with Cambridge mark scheme…" : "Submit Chief Examiner Verdict ⚖️"}
                  </Button>
                </div>

                {error ? <ErrorNote error={error} /> : null}

                {/* Verdict Display */}
                {verdict && (
                  <div
                    className={`p-4 rounded-2xl border-2 space-y-2.5 animate-fadeIn ${
                      verdict.success
                        ? "border-emerald-300 bg-emerald-50 text-emerald-950"
                        : "border-rose-300 bg-rose-50 text-rose-950"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{verdict.success ? "🏆" : "🤔"}</span>
                        <div className="font-fun font-bold text-sm">
                          {verdict.success ? "Outstanding Diagnosis!" : "Close, but re-read the steps!"}
                        </div>
                      </div>
                      <span className="text-xs font-fun font-extrabold px-2.5 py-0.5 rounded-full bg-white/80 border border-slate-300">
                        Score: {verdict.score}/100
                      </span>
                    </div>

                    <p className="text-xs leading-relaxed font-medium">
                      {verdict.examiner_report}
                    </p>

                    <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-xs font-semibold">
                      <span>Official Cambridge Mark:</span>
                      <span className="font-fun font-bold">{verdict.official_mark}</span>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      ) : (
        <Empty>No bug challenges loaded for this subject yet.</Empty>
      )}
    </div>
  );
}
