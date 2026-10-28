"use client";

import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { AssessmentBrief } from "@/lib/api";
import { KIND_LABELS, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

type Score = { awarded: number; available: number; ratio: number; provisional: boolean } | null;
type Arm = { pair_code: string; arm: string; objective_codes: string[]; baseline: Score; post: Score; retention: Score; gain: number | null; retention_ratio: number | null; eligible: boolean | null };
type Results = {
  decision: string;
  reasons: string[];
  provisional: boolean;
  sessions_per_week: number | null;
  app_hours: number;
  gain_difference: number | null;
  arms: Arm[];
  forms: { kind: string; form_code: string | null; submitted_at: string }[];
};

const DECISION: Record<string, { tone: "good" | "warn" | "neutral" | "alert"; label: string }> = {
  pending: { tone: "neutral", label: "Waiting for tests" },
  go_candidate: { tone: "good", label: "Looks like GO (interview still needed)" },
  iterate: { tone: "warn", label: "ITERATE" },
  no_gain: { tone: "alert", label: "No gain yet" },
};

const pct = (s: Score) => (s ? `${s.awarded}/${s.available}${s.provisional ? "*" : ""}` : "–");
const num = (n: number | null) => (n === null ? "–" : n.toFixed(2));

function StudyResults({ subjectId, subjectName, query }: { subjectId: string; subjectName: string; query: string }) {
  const results = useApi<Results>(`/studies/${subjectId}/results?${query}`);
  const r = results.data;
  if (results.error) return <ErrorNote error={results.error} />;
  if (!r) return null;
  const decision = DECISION[r.decision] ?? { tone: "neutral" as const, label: r.decision };
  return (
    <Card
      title={`🔬 Validation Study · ${subjectName}`}
      subtitle={`Empirical efficacy check comparing baseline, post-test, and 2-week retention gains. ${r.provisional ? "(* Includes marks not yet final)." : ""}`}
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="flex flex-col rounded-2xl border border-line-soft bg-white p-3 shadow-xs">
          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">Evaluation Status</span>
          <div className="mt-1">
            <Chip tone={decision.tone}>{decision.label}</Chip>
          </div>
        </div>
        <div className="flex flex-col rounded-2xl border border-line-soft bg-white p-3 shadow-xs">
          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">Gain Difference</span>
          <span className="font-fun text-xl font-extrabold text-ink mt-0.5">{num(r.gain_difference)}</span>
          <span className="text-[10px] text-muted">treatment vs control</span>
        </div>
        <div className="flex flex-col rounded-2xl border border-line-soft bg-white p-3 shadow-xs">
          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">Pace</span>
          <span className="font-fun text-xl font-extrabold text-ink mt-0.5">{num(r.sessions_per_week)}</span>
          <span className="text-[10px] text-muted">sessions / week</span>
        </div>
        <div className="flex flex-col rounded-2xl border border-line-soft bg-white p-3 shadow-xs">
          <span className="text-[11px] font-bold text-muted uppercase tracking-wider">Total Time</span>
          <span className="font-fun text-xl font-extrabold text-ink mt-0.5">{r.app_hours.toFixed(1)} hrs</span>
          <span className="text-[10px] text-muted">in active practice</span>
        </div>
      </div>

      {r.arms.length === 0 ? (
        <Empty>No topic pairs set up yet for this subject.</Empty>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-line-soft bg-white shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-xs">
              <thead className="bg-[#FAF7F0] text-muted uppercase tracking-wider font-bold text-[10px]">
                <tr>
                  <th className="py-3 px-4">Topic Pair</th>
                  <th className="py-3 px-2">Study Arm</th>
                  <th className="py-3 px-2">Objectives</th>
                  <th className="py-3 px-2">Baseline</th>
                  <th className="py-3 px-2">Post-Test</th>
                  <th className="py-3 px-2">Retention</th>
                  <th className="py-3 px-2">Absolute Gain</th>
                  <th className="py-3 px-4">Retention Ratio</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line-soft text-ink-2">
                {r.arms.map((a) => (
                  <tr key={`${a.pair_code}${a.arm}`} className="hover:bg-sand/30 transition">
                    <td className="py-3 px-4 font-bold text-ink">{a.pair_code}</td>
                    <td className="py-3 px-2">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        a.arm.toLowerCase().includes("treatment") || a.arm.toLowerCase().includes("a") ? "bg-purple-100 text-purple-800" : "bg-amber-100 text-amber-800"
                      }`}>
                        {a.arm}
                      </span>
                    </td>
                    <td className="py-3 px-2 font-mono text-[11px]">{a.objective_codes.join(", ")}</td>
                    <td className="py-3 px-2 font-semibold">
                      {pct(a.baseline)} {a.eligible === false ? <span className="text-[10px] text-warn font-normal">(outside 20–70%)</span> : null}
                    </td>
                    <td className="py-3 px-2 font-semibold">{pct(a.post)}</td>
                    <td className="py-3 px-2 font-semibold">{pct(a.retention)}</td>
                    <td className="py-3 px-2 font-fun font-bold text-ink">{num(a.gain)}</td>
                    <td className="py-3 px-4 font-fun font-bold text-ink">{num(a.retention_ratio)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {r.reasons.length > 0 && (
        <div className="rounded-xl bg-amber-50/60 p-3 text-[11px] text-amber-900 border border-slate-200/50">
          <span className="font-bold">Evaluation Criteria Notes:</span> {r.reasons.map((x) => x.replaceAll("_", " ")).join("; ")}
        </div>
      )}
    </Card>
  );
}

export default function ParentTests() {
  const { id, query, subjects } = useLinkedStudent();
  const list = useApi<AssessmentBrief[]>(id ? `/assessments?${query}` : null);
  const names = Object.fromEntries(subjects.map((s) => [s.subject_id, s.subject_name]));
  return (
    <div className="flex flex-col gap-6">
      {/* Friendly banner */}
      <section className="relative overflow-hidden rounded-3xl border border-purple-100 bg-gradient-to-r from-[#F5F3FF] via-[#FAF5FF] to-[#FFF9F2] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-purple-800 shadow-xs">
              <span>📊</span> Research Validation & Tests
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              Formal Assessments & Study Efficacy
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Review Cambridge past-paper test forms and track empirical learning gain calculations between baseline, immediate post-tests, and two-week retention.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-purple-200/60 bg-white/90 p-4 shadow-xs">
            <div className="text-3xl">📐</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Cambridge Standard</div>
              <div className="font-fun text-sm font-bold text-ink">Mark Scheme Verified</div>
              <div className="text-[11px] text-muted">Reserved past-paper forms</div>
            </div>
          </div>
        </div>
      </section>

      <Card
        title="📝 Test Forms"
        subtitle="Formal test forms assembled from reserved Cambridge past-paper questions to measure genuine retention without prompt leakage."
      >
        {list.error ? <ErrorNote error={list.error} /> : null}
        {list.data?.length === 0 && <Empty>No formal tests recorded yet.</Empty>}
        <ul className="flex flex-col gap-2.5">
          {list.data?.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line-soft bg-white/80 p-3.5 shadow-xs transition hover:border-brand/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-700 font-bold text-sm">
                ✍️
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-ink">
                    {names[a.subject_id] ?? "Subject"} · {KIND_LABELS[a.kind] ?? a.kind}
                  </span>
                  {a.form_code && (
                    <span className="rounded-full bg-sand px-2 py-0.5 text-xs font-mono font-semibold text-ink-2">
                      Form {a.form_code}
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-muted">
                  🎯 {a.total_marks} marks total · {a.submitted_at ? `Submitted ${shortDate(a.submitted_at)}` : `Status: ${a.status.replace("_", " ")}`}
                </div>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-bold ${
                a.submitted_at ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
              }`}>
                {a.submitted_at ? "Completed" : "In Progress"}
              </span>
            </li>
          ))}
        </ul>
      </Card>

      {id && subjects.map((s) => <StudyResults key={s.subject_id} subjectId={s.subject_id} subjectName={s.subject_name} query={query} />)}
    </div>
  );
}
