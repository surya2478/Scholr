import type { Evaluation } from "@/lib/api";
import { ExaminerInsights } from "./ExaminerInsights";
import { MathText } from "./MathText";
import { Chip } from "./ui";

export function EvaluationCard({ evaluation }: { evaluation: Evaluation }) {
  const full = evaluation.marks_awarded === evaluation.marks_available;
  const percentage = evaluation.marks_available > 0 ? Math.round((evaluation.marks_awarded / evaluation.marks_available) * 100) : 0;

  return (
    <div className="flex flex-col gap-3.5 rounded-3xl border-2 border-amber-300/80 bg-[#FFFDF9] p-5 shadow-sm space-y-1">
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

      <ExaminerInsights evaluationId={evaluation.id} />
    </div>
  );
}
