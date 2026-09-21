"use client";

import type { ExaminerInsight, ExaminerInsights as Insights } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// What Cambridge's examiners said about this question in their report (AC-R6). Shown only with a marked
// answer — the API serves it through the evaluation — and always attributed, never as Scholr's own advice.
const LABELS: Record<ExaminerInsight["kind"], { icon: string; label: string }> = {
  common_error: { icon: "✗", label: "Lost marks" },
  what_scored: { icon: "✓", label: "Scored" },
  advice: { icon: "→", label: "Advice" },
};

function Point({ point }: { point: ExaminerInsight }) {
  const { icon, label } = LABELS[point.kind];
  return (
    <li className="flex gap-2">
      <span className="shrink-0 w-4 text-center font-bold text-slate-500" aria-label={label} title={label}>
        {icon}
      </span>
      <span className="leading-relaxed">{point.text}</span>
    </li>
  );
}

export function ExaminerInsights({ evaluationId }: { evaluationId: string }) {
  const { data } = useApi<Insights>(`/evaluations/${evaluationId}/examiner-insights`);
  return data ? <ExaminerInsightsView data={data} /> : null;
}

// The same points, when the page already has them: the worked exam question on a topic page (AC-U16) shows its
// answer, so what the examiners said about it can be shown with it.
export function ExaminerInsightsView({ data }: { data: Insights }) {
  if (data.question.length === 0 && data.paper.length === 0) return null;
  const source = (data.question[0] ?? data.paper[0]).attribution.split(" — ")[0];

  return (
    <details className="p-3 rounded-2xl bg-sky-50 border border-sky-200 text-xs text-slate-800 group">
      <summary className="flex cursor-pointer items-center gap-1.5 font-fun font-bold text-sky-900 list-none">
        <span>📋</span> What the examiners said about this question
        <span className="ml-auto text-sky-700 group-open:rotate-90 transition-transform">›</span>
      </summary>
      <div className="mt-2.5 space-y-2.5">
        {data.question.length > 0 && (
          <ul className="space-y-1.5">
            {data.question.map((p, i) => (
              <Point key={i} point={p} />
            ))}
          </ul>
        )}
        {data.paper.length > 0 && (
          <div className="space-y-1.5">
            <div className="font-semibold text-sky-900">On the whole paper</div>
            <ul className="space-y-1.5">
              {data.paper.map((p, i) => (
                <Point key={i} point={p} />
              ))}
            </ul>
          </div>
        )}
        <p className="text-[11px] text-slate-500 border-t border-sky-100 pt-2">
          Source: {source}. {data.note}
        </p>
      </div>
    </details>
  );
}
