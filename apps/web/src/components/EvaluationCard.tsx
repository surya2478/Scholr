import { useState } from "react";
import { api, type Evaluation } from "@/lib/api";
import { ExaminerInsights } from "./ExaminerInsights";
import { MathText } from "./MathText";
import { Button, Chip } from "./ui";

export function EvaluationCard({
  evaluation,
  confidence,
}: {
  evaluation: Evaluation;
  confidence?: number | null;
}) {
  const full = evaluation.marks_awarded === evaluation.marks_available;
  const percentage = evaluation.marks_available > 0 ? Math.round((evaluation.marks_awarded / evaluation.marks_available) * 100) : 0;
  const isBlindspot = confidence !== undefined && confidence !== null && confidence >= 3 && percentage < 70;
  const isHesitant = confidence !== undefined && confidence !== null && confidence <= 2 && percentage >= 70;
  const isCalibrated = confidence !== undefined && confidence !== null && confidence >= 3 && percentage >= 70;

  const [autopsy, setAutopsy] = useState(evaluation.feedback.autopsy ?? null);
  const [category, setCategory] = useState("conceptual");
  const [takeaway, setTakeaway] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSaveAutopsy() {
    if (!takeaway.trim()) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api<Evaluation>(`/evaluations/${evaluation.id}/autopsy`, {
        method: "POST",
        json: { category, takeaway: takeaway.trim() },
      });
      if (updated.feedback.autopsy) setAutopsy(updated.feedback.autopsy);
      else setSaveError("It didn't save. Try again in a moment.");
    } catch {
      // Never show "saved" for something that was not: she would rely on a diary entry that does not exist.
      setSaveError("It didn't save. Check your connection and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-3.5 rounded-3xl border-2 border-amber-300/80 bg-[#FFFDF9] p-5 shadow-sm space-y-1">
      {/* Metacognitive Calibration Alert */}
      {isBlindspot && (
        <div className="flex items-start gap-2.5 p-3 rounded-2xl bg-rose-50 border border-rose-300 text-xs text-rose-950 font-medium">
          <span className="text-lg flex-none">⚠️</span>
          <div>
            <div className="font-fun font-bold text-rose-900">
              Metacognitive Epistemic Trap (Blindspot)
            </div>
            <div>
              You felt very confident before solving, but lost marks here. This is the exact kind of trick question Cambridge examiners use to distinguish A from A* candidates! Pay close attention to the mistakes diagnosed below.
            </div>
          </div>
        </div>
      )}

      {isHesitant && (
        <div className="flex items-start gap-2.5 p-3 rounded-2xl bg-indigo-50 border border-indigo-200 text-xs text-indigo-950 font-medium">
          <span className="text-lg flex-none">🌟</span>
          <div>
            <div className="font-fun font-bold text-indigo-900">
              Hesitant Victory! (Trust Your Knowledge)
            </div>
            <div>
              You felt unsure before solving, yet your working earned top marks! Your intuition and preparation are stronger than you thought.
            </div>
          </div>
        </div>
      )}

      {isCalibrated && (
        <div className="flex items-center gap-2 p-2.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 font-medium">
          <span className="text-base flex-none">🎯</span>
          <span>
            <strong>Spot On Calibration:</strong> High confidence backed by high marks!
          </span>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-amber-100 pb-3">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl select-none">{full ? "🎉" : percentage >= 50 ? "⭐" : "💡"}</span>
          <div>
            <div className="text-lg font-fun font-bold text-slate-900 leading-tight">
              {evaluation.marks_awarded} / {evaluation.marks_available} Marks Scored
            </div>
            <div className="text-[11px] text-slate-500 font-medium">Official Cambridge Mark Scheme Evaluation</div>
          </div>
        </div>
        <div>
          {evaluation.provisional ? (
            <Chip tone="warn">Provisional · parent review</Chip>
          ) : evaluation.status === "overridden" ? (
            <Chip tone="brand">Checked by parent ✓</Chip>
          ) : (
            <Chip tone={full ? "good" : "neutral"}>{full ? "Full marks! 🌟" : `${percentage}%`}</Chip>
          )}
        </div>
      </div>

      {evaluation.feedback.summary && (
        <div className="text-sm font-medium text-slate-700 bg-white p-3 rounded-2xl border border-amber-100">
          <MathText text={evaluation.feedback.summary} />
        </div>
      )}

      {evaluation.feedback.what_went_well && (
        <div className="p-3 rounded-2xl bg-emerald-50 border border-emerald-200 text-xs text-slate-800 space-y-1">
          <div className="flex items-center gap-1.5 font-fun font-bold text-emerald-800">
            <span>✨</span> What went well
          </div>
          <MathText text={evaluation.feedback.what_went_well} className="leading-relaxed" />
        </div>
      )}

      {evaluation.mistakes.map((m, i) => (
        <div key={i} className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-slate-800 space-y-1">
          <div className="flex items-center gap-1.5 font-fun font-bold text-amber-900">
            <span>⚠️</span> Watch out for this trap
          </div>
          <MathText text={m.description} className="leading-relaxed" />
        </div>
      ))}

      {evaluation.feedback.next_step && (
        <div className="p-3 rounded-2xl bg-orange-50 border border-orange-200 text-xs text-orange-900 space-y-1">
          <div className="flex items-center gap-1.5 font-fun font-bold text-orange-800">
            <span>🎯</span> Recommended next step
          </div>
          <MathText text={evaluation.feedback.next_step} className="leading-relaxed font-medium" />
        </div>
      )}

      {/* Metacognitive Error Autopsy (Kota/Kumon Error Diary) */}
      {!full && (
        <>
          {autopsy ? (
            <div className="p-4 rounded-2xl bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 text-xs space-y-1.5 shadow-2xs">
              <div className="flex items-center justify-between">
                <span className="font-fun font-bold text-purple-900 flex items-center gap-1.5">
                  <span>📔</span> My Error Autopsy Rule Recorded
                </span>
                <span className="px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold uppercase border border-purple-200">
                  {autopsy.category}
                </span>
              </div>
              <p className="text-slate-800 font-medium italic">
                &ldquo;{autopsy.takeaway}&rdquo;
              </p>
              <div className="text-[10px] text-purple-700 font-semibold flex items-center gap-1">
                <span>✓</span> Saved to your Personal Error Diary (reviewable before exams)
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-2xl bg-gradient-to-br from-amber-50/90 via-orange-50/70 to-purple-50/80 border-2 border-dashed border-orange-300 text-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🩺</span>
                  <div>
                    <span className="font-fun font-bold text-slate-900 text-sm block">
                      Conduct Error Autopsy
                    </span>
                    <span className="text-[11px] text-slate-500 font-medium">
                      Self-diagnosing why you missed marks builds an immune system against repeating errors.
                    </span>
                  </div>
                </div>
                <span className="text-[10.5px] font-fun font-bold text-orange-700 bg-orange-100 px-2 py-0.5 rounded-full border border-orange-200">
                  Metacognitive Diary
                </span>
              </div>

              <div className="space-y-1.5">
                <span className="font-fun font-bold text-slate-700 text-[11px] block">
                  1. Root Cause Diagnosis:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {[
                    { id: "conceptual", label: "Conceptual / Formula Gap", emoji: "🧠", desc: "Didn't know/recall the core theorem" },
                    { id: "calculation", label: "Calculation / Sign Slip", emoji: "✏️", desc: "Understood method, made arithmetic slip" },
                    { id: "misreading", label: "Question Misread / Command Word", emoji: "🔍", desc: "Missed 3 s.f., units, or command nuance" },
                    { id: "strategy", label: "Strategic / Time Impasse", emoji: "⏱️", desc: "Stuck on approach or ran out of time" },
                  ].map((cat) => (
                    <button
                      type="button"
                      key={cat.id}
                      onClick={() => setCategory(cat.id)}
                      className={`p-2 rounded-xl text-left border transition-all cursor-pointer ${
                        category === cat.id
                          ? "border-orange-500 bg-white text-orange-950 shadow-2xs scale-[1.01]"
                          : "border-amber-200/80 bg-white/70 text-slate-600 hover:bg-white"
                      }`}
                    >
                      <div className="font-fun font-bold text-[11px] flex items-center gap-1.5">
                        <span>{cat.emoji}</span>
                        <span>{cat.label}</span>
                      </div>
                      <div className="text-[10px] text-slate-500 line-clamp-1 mt-0.5">{cat.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1.5">
                <span className="font-fun font-bold text-slate-700 text-[11px] block">
                  2. Your Personal Takeaway (What rule will you remember next time?):
                </span>
                <input
                  type="text"
                  value={takeaway}
                  onChange={(e) => setTakeaway(e.target.value)}
                  placeholder="e.g., Must factorise numerator before cancelling; watch -2 * -4 = +8"
                  className="w-full h-9 rounded-xl border border-amber-300 bg-white px-3 text-xs font-medium text-slate-900 outline-none focus:border-orange-500"
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
                <Button
                  disabled={saving || !takeaway.trim()}
                  onClick={handleSaveAutopsy}
                  className="text-xs py-1.5 px-3.5"
                >
                  {saving ? "Saving to Diary…" : "Save Rule to Personal Error Diary 📔"}
                </Button>
                {saveError && <span className="text-[11px] font-semibold text-rose-700">{saveError}</span>}
                <span className="text-[10.5px] text-slate-400 italic">
                  Saved directly to your personal Mistakes Diary
                </span>
              </div>
            </div>
          )}
        </>
      )}

      <ExaminerInsights evaluationId={evaluation.id} />
    </div>
  );
}

