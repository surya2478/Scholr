"use client";

import { useState } from "react";
import { Button, Card, Chip, Empty, ErrorNote, Stat } from "@/components/ui";
import type { MonthlySummary } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

const percent = (value: number | null) => (value === null ? "—" : `${Math.round(value * 100)}%`);
const duration = (minutes: number) => (minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`);
const monthName = (month: string) => new Date(`${month}-01T12:00:00`).toLocaleDateString(undefined, { month: "long", year: "numeric" });

// Monthly summary for the parent: patterns over a calendar month, built from marked work, sessions and plans.
export default function MonthlySummaryPage() {
  const { student, id } = useLinkedStudent();
  const [month, setMonth] = useState<string | null>(null);
  const summary = useApi<MonthlySummary>(id ? `/guardian/students/${id}/monthly${month ? `?month=${month}` : ""}` : null);

  if (!student) return <Empty>No student is linked to this account.</Empty>;
  const m = summary.data;
  const first = student.display_name.split(" ")[0];

  return (
    <div className="space-y-6">
      {/* Warm Header Banner */}
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
              <span>📅</span> Monthly Learning Report
            </span>
            <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
              {m ? monthName(m.month) : "Monthly Summary"}
            </h1>
            <p className="text-xs md:text-sm text-slate-600 font-medium">
              Aggregated patterns from marked work, practice sessions, and completed plans.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="secondary" disabled={!m} onClick={() => m && setMonth(m.previous_month)}>
              ← Previous
            </Button>
            <Button variant="secondary" disabled={!m?.next_month} onClick={() => m?.next_month && setMonth(m.next_month)}>
              Next →
            </Button>
          </div>
        </div>
      </div>

      {summary.error ? <ErrorNote error={summary.error} /> : null}

      {m && (
        <>
          <Card
            title={`${first}'s Month at a Glance`}
            subtitle={`${m.days_counted} day(s) of ${monthName(m.month)} evaluated, compared with ${monthName(m.previous_month)}`}
          >
            <div className="grid grid-cols-2 gap-3.5 md:grid-cols-4 pt-1">
              <Stat label="Days studied" value={`${m.totals.active_days} of ${m.days_counted}`} icon="📅" hint={`Last month: ${m.previous.active_days}`} />
              <Stat label="Study time" value={duration(m.totals.study_minutes)} icon="🕒" hint={`Last month: ${duration(m.previous.study_minutes)}`} />
              <Stat label="Answers marked" value={String(m.totals.answers_marked)} icon="📝" hint={`Last month: ${m.previous.answers_marked}`} />
              <Stat label="Marks scored" value={percent(m.totals.accuracy)} icon="🎯" hint={`Last month: ${percent(m.previous.accuracy)}`} />
            </div>
          </Card>

          <Card
            title="Subject Performance Matrix"
            subtitle="Checked marks only. Answering without hints means solved unassisted or with only a tiny nudge."
          >
            {m.subjects.length === 0 ? (
              <Empty>No subjects recorded for this month.</Empty>
            ) : (
              <div className="overflow-x-auto pt-1">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="text-[11px] font-fun font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                    <tr>
                      <th className="py-3 pr-3">Subject</th>
                      <th className="py-3 pr-3">Answers Marked</th>
                      <th className="py-3 pr-3">Marks Scored</th>
                      <th className="py-3 pr-3">Unassisted %</th>
                      <th className="py-3 pr-3">Sessions & Time</th>
                      <th className="py-3 pr-3">Mistakes Found / Fixed</th>
                      <th className="py-3">Topics Secured</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {m.subjects.map((s) => (
                      <tr key={s.subject_id} className="hover:bg-amber-50/40 transition-colors">
                        <td className="py-3.5 pr-3 font-fun font-bold text-slate-900 text-sm">{s.subject_name}</td>
                        <td className="py-3.5 pr-3 font-medium text-slate-700">
                          {s.answers_marked}
                          {s.awaiting_review > 0 && (
                            <span className="ml-1 text-xs font-bold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">
                              ({s.awaiting_review} to check)
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 pr-3 font-medium text-slate-700">
                          <span className="font-bold text-slate-900">{percent(s.accuracy)}</span>
                          {s.marks_available > 0 && (
                            <span className="ml-1 text-xs text-slate-400">
                              ({s.marks_awarded}/{s.marks_available})
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 pr-3 font-bold text-emerald-700">{percent(s.independent_share)}</td>
                        <td className="py-3.5 pr-3 font-medium text-slate-700">
                          {s.sessions} sessions · {duration(s.study_minutes)}
                        </td>
                        <td className="py-3.5 pr-3 font-medium text-slate-700">
                          <span className="text-amber-700">{s.mistakes_found} found</span> / <span className="text-emerald-700 font-bold">{s.mistakes_resolved} fixed</span>
                        </td>
                        <td className="py-3.5 font-fun font-bold text-slate-900">{s.topics_secured ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {m.plan_items_total !== null && (
            <Card title="Daily plans">
              <p className="text-sm text-ink-2">
                {m.plan_items_total === 0
                  ? "No plan items this month."
                  : `${m.plan_items_completed} of ${m.plan_items_total} plan items done${m.plan_items_skipped ? `, ${m.plan_items_skipped} skipped` : ""}.`}
              </p>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            {m.secured && (
              <Card title="Topics secured" subtitle="Shown at competent or better this month.">
                {m.secured.length === 0 && <p className="text-sm text-muted">None this month yet.</p>}
                <ul className="flex flex-col gap-2">
                  {m.secured.map((w) => (
                    <li key={w.objective_code} className="flex items-center gap-2 rounded-xl border border-line-soft px-3 py-2 text-xs">
                      <span className="min-w-0 flex-1 truncate">
                        {w.objective_code} {w.objective_statement}
                      </span>
                      <Chip tone="brand">{w.level_name}</Chip>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
            {m.focus && (
              <Card title="Worth a conversation" subtitle="Recurring mistakes and topics due for review, as of today.">
                {m.focus.length === 0 && <p className="text-sm text-muted">Nothing flagged.</p>}
                <ul className="flex flex-col gap-2">
                  {m.focus.map((f, i) => (
                    <li key={i} className="flex items-center gap-2 rounded-xl border border-line-soft px-3 py-2 text-xs">
                      <span className="min-w-0 flex-1 truncate">
                        {f.objective_code ? `${f.objective_code} ` : ""}
                        {f.label}
                      </span>
                      <Chip tone="warn">{f.kind === "mistake" ? "Recurring" : "Review due"}</Chip>
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  );
}
