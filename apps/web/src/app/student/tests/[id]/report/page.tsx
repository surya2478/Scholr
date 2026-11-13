"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Button, Card, Chip, ErrorNote } from "@/components/ui";
import { type AssessmentReport } from "@/lib/api";
import { useApi } from "@/lib/useApi";

export default function AssessmentReportPage() {
  const { id } = useParams<{ id: string }>();
  const reportQuery = useApi<AssessmentReport>(`/assessments/${id}/report`);
  const r = reportQuery.data;

  if (reportQuery.error) return <ErrorNote error={reportQuery.error} />;
  if (!r) return <p className="text-sm text-slate-500 py-10 text-center">Loading in-depth performance diagnostic…</p>;

  const paceColor =
    r.pacing.pace_status === "optimal"
      ? "text-emerald-700 bg-emerald-100 border-emerald-300"
      : r.pacing.pace_status === "rushed"
      ? "text-amber-700 bg-amber-100 border-amber-300"
      : "text-rose-700 bg-rose-100 border-rose-300";

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="rounded-3xl border-2 border-indigo-200 bg-gradient-to-br from-indigo-50 via-[#F3F4FF] to-blue-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <Link
              href={`/student/tests/${id}`}
              className="inline-flex items-center gap-1 text-xs font-fun font-bold text-indigo-600 hover:text-indigo-700 bg-white/90 border border-indigo-200 px-3 py-1 rounded-xl mb-2"
            >
              ← Back to Test Questions
            </Link>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              {r.title} — Detailed Performance Analysis 📊
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium">
              Your marks, your pacing and where the time went. No grade is shown: Cambridge sets new grade boundaries for every paper in every series.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href={`/student/tutor?prompt=I just finished ${encodeURIComponent(r.title)} and scored ${r.total_marks_awarded}/${r.total_marks_available}. Can we do a quick strategic debrief on where I spent too much time?`}
              className="px-4 py-2 rounded-2xl font-fun font-bold text-xs bg-indigo-600 hover:bg-indigo-700 text-white shadow-xs"
            >
              🎓 Post-Mock Debrief with Tutor
            </Link>
          </div>
        </div>
      </div>

      {/* 1. Marks, pacing and time sinks */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-3xl bg-white border-2 border-emerald-200 shadow-2xs space-y-1">
          <span className="text-xs font-medium text-slate-500 block">Total Score</span>
          <div className="text-2xl md:text-3xl font-fun font-bold text-emerald-700">
            {r.total_marks_awarded} <span className="text-sm font-normal text-slate-400">/ {r.total_marks_available}</span>
          </div>
          <span className="text-xs font-bold text-emerald-800">{r.score_percentage}% awarded</span>
        </div>

        <div className="p-5 rounded-3xl bg-white border-2 border-slate-200 shadow-2xs space-y-1">
          <span className="text-xs font-medium text-slate-500 block">Pacing &amp; Speed</span>
          <div className="text-2xl md:text-3xl font-fun font-bold text-amber-800">
            {r.pacing.avg_time_per_mark_s}s <span className="text-xs font-normal text-slate-400">/ mark</span>
          </div>
          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold border ${paceColor}`}>
            {r.pacing.pace_status.toUpperCase()} (Target: ~{r.pacing.target_pace_s_per_mark}s)
          </span>
        </div>

        <div className="p-5 rounded-3xl bg-white border-2 border-purple-200 shadow-2xs space-y-1">
          <span className="text-xs font-medium text-slate-500 block">Time Sinks Detected</span>
          <div className="text-2xl md:text-3xl font-fun font-bold text-purple-800">
            {r.time_sinks.length}
          </div>
          <span className="text-[11px] text-purple-700 font-medium">Questions with high time penalty</span>
        </div>
      </div>

      {/* 2. Prescribed Tactical Action Plan */}
      {r.action_plan.length > 0 && (
        <div className="p-5 rounded-3xl border-2 border-amber-300 bg-amber-50/70 space-y-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎯</span>
            <h3 className="text-sm font-fun font-bold text-amber-950 uppercase tracking-wider">
              Prescribed Tactical Next Steps
            </h3>
          </div>
          <ul className="space-y-1.5 pl-6 list-disc text-xs md:text-sm text-slate-800 font-medium">
            {r.action_plan.map((act, idx) => (
              <li key={idx}>{act}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 3. Time Sinks & Triage Analysis */}
      <Card
        title="Question Pacing &amp; Time-Sink Analysis ⏱️"
        subtitle="Questions where over 90s/mark was spent but scored below 50% marks"
      >
        {r.time_sinks.length === 0 ? (
          <div className="p-4 rounded-2xl bg-emerald-50 text-emerald-800 text-xs font-medium border border-emerald-200">
            ✓ Excellent triage! You had zero severe time-sinks in this sitting. You avoided getting stuck on low-yield questions.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {r.time_sinks.map((ts) => (
                <div
                  key={ts.position}
                  className="p-4 rounded-2xl bg-rose-50/60 border border-rose-200 space-y-2 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-fun font-bold text-rose-900">
                      Question {ts.position}
                    </span>
                    <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 font-bold text-[10px]">
                      {ts.pace_seconds_per_mark}s per mark
                    </span>
                  </div>
                  <p className="text-slate-700 font-mono text-[11px] line-clamp-2">
                    {ts.stem_snippet}
                  </p>
                  <div className="flex items-center justify-between pt-1 border-t border-rose-200/60 text-[11px] text-slate-600">
                    <span>Awarded: <b>{ts.marks_awarded} / {ts.marks_available}</b></span>
                    <span>Time Spent: <b>{Math.round(ts.time_spent_s / 60)}m {ts.time_spent_s % 60}s</b></span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 italic mt-2">
              💡 Tip: In Cambridge exams, remember the 2-Pass Rule: If you reach 3 minutes on a question with no clear method, star it and move forward.
            </p>
          </div>
        )}
      </Card>

      {/* 4. Syllabus Topic Mastery Matrix */}
      <Card
        title="Syllabus &amp; Topic Diagnostic Matrix 🗺️"
        subtitle="Topic-wise score contribution and accuracy"
      >
        <div className="space-y-3">
          {r.topic_breakdown.map((t) => {
            const badgeTone =
              t.status === "mastered" ? "bg-emerald-100 text-emerald-800 border-emerald-300" :
              t.status === "solid" ? "bg-blue-100 text-blue-800 border-blue-300" :
              "bg-rose-100 text-rose-800 border-rose-300";
            return (
              <div
                key={t.topic_id}
                className="p-4 rounded-2xl border border-slate-200 bg-white space-y-2 text-xs"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-slate-500 text-[11px]">{t.code}</span>
                    <span className="font-fun font-bold text-slate-900 text-sm">{t.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-600">
                      {t.marks_awarded} / {t.marks_available} marks
                    </span>
                    <span className={`px-2 py-0.5 rounded-full font-bold border text-[10px] ${badgeTone}`}>
                      {t.accuracy_pct}% ({t.status.replace("_", " ")})
                    </span>
                  </div>
                </div>
                {/* Progress Bar */}
                <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      t.status === "mastered" ? "bg-emerald-500" :
                      t.status === "solid" ? "bg-blue-500" : "bg-rose-500"
                    }`}
                    style={{ width: `${Math.max(t.accuracy_pct, 4)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      {/* 5. Cognitive Difficulty Tier Conversion */}
      <Card
        title="Question Difficulty Conversion 🎯"
        subtitle="Performance across foundation recall vs multi-step application vs non-routine problems"
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {r.difficulty_breakdown.map((d) => (
            <div
              key={d.tier}
              className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2 text-xs"
            >
              <span className="font-fun font-bold text-slate-800 block text-sm">{d.label}</span>
              <div className="text-xl font-bold font-mono text-slate-900">
                {d.marks_awarded} / {d.marks_available}
              </div>
              <div className="w-full h-1.5 rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-full bg-indigo-600 rounded-full"
                  style={{ width: `${Math.max(d.accuracy_pct, 4)}%` }}
                />
              </div>
              <span className="text-[11px] text-slate-500 block font-medium">
                Accuracy: <b>{d.accuracy_pct}%</b>
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
