"use client";

import Link from "next/link";
import { DayBars, HelpMixBars, TrendLine } from "@/components/Charts";
import { DayTimeline } from "@/components/DayTimeline";
import { DinnerStartersCard, type ConversationStarter } from "@/components/DinnerStartersCard";
import { WorkloadGuardrail } from "@/components/WorkloadGuardrail";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { ExternalSummary, GuardianOverview, MonthlySummary, Plan, Trends } from "@/lib/api";
import { dateTime, minutes } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

const percent = (value: number | null | undefined) => (value === null || value === undefined ? "—" : `${Math.round(value * 100)}%`);
const weekLabel = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });

function Tile({ question, value, unit, note, tone = "muted" }: { question: string; value: string; unit?: string; note?: string; tone?: "good" | "muted" }) {
  return (
    <div className="flex min-h-[96px] flex-col gap-1 rounded-2xl bg-white border border-slate-200/90 p-4 shadow-2xs hover:border-blue-400 transition-colors">
      <span className="text-xs font-semibold text-slate-500">{question}</span>
      <span className="flex items-baseline gap-1.5 my-0.5">
        <span className="text-2xl font-fun font-bold leading-tight text-slate-900">{value}</span>
        {unit && <span className="text-xs font-semibold text-slate-600">{unit}</span>}
      </span>
      {note && <span className={`mt-auto text-[11px] font-bold ${tone === "good" ? "text-emerald-700" : "text-slate-400"}`}>{note}</span>}
    </div>
  );
}

// Workload: how this week's average day compares with the family's own plan.
function workload(actualPerDay: number, plannedPerDay: number): { value: string; note: string } {
  if (!plannedPerDay) return { value: "Not set", note: "Add study time to the schedule to compare" };
  const share = actualPerDay / plannedPerDay;
  const note = `About ${minutes(Math.round(actualPerDay))} a day, plan is ${minutes(plannedPerDay)}`;
  if (share < 0.65) return { value: "Light", note };
  if (share > 1.35) return { value: "Heavy", note };
  return { value: "Balanced", note };
}

export default function ParentOverview() {
  const { student, id, query, has } = useLinkedStudent();
  const overview = useApi<GuardianOverview>(id ? `/guardian/students/${id}/overview` : null);
  const external = useApi<ExternalSummary>(id ? `/external-training/summary?${query}&weeks=4` : null);
  const monthly = useApi<MonthlySummary>(id ? `/guardian/students/${id}/monthly` : null);
  const trends = useApi<Trends>(id ? `/guardian/students/${id}/trends?weeks=8` : null);
  const plan = useApi<Plan>(id && has("plans") ? `/plan/today?${query}` : null);

  if (!student) return <Empty>No student is linked to this account.</Empty>;
  const o = overview.data;
  const m = monthly.data;
  const t = trends.data;
  const first = student.display_name.split(" ")[0];

  const subjects = o?.summary.subjects ?? [];
  const secure = subjects.reduce((n, s) => n + s.competent_or_better, 0);
  const totalTopics = subjects.reduce((n, s) => n + s.objectives_total, 0);
  const weeks = t?.weeks ?? [];
  const labels = weeks.map((w) => weekLabel(w.week_start));
  const answered = weeks.filter((w) => w.answers_marked > 0);
  const secureDelta = weeks.length > 1 && weeks[0].topics_secure !== null && weeks.at(-1)!.topics_secure !== null ? weeks.at(-1)!.topics_secure! - weeks[0].topics_secure! : null;
  const independentNow = answered.at(-1)?.independent_share ?? null;
  const independentThen = answered.length > 1 ? answered[0].independent_share : null;
  const perDay = t ? t.days.reduce((n, d) => n + d.study_minutes, 0) / 7 : 0;
  const load = workload(perDay, t?.planned_minutes_per_day ?? 0);

  // Dynamic conversation prompts for dinner table
  const starters: ConversationStarter[] = [];
  if (o?.summary.recent_wins && o.summary.recent_wins.length > 0) {
    const win = o.summary.recent_wins[0];
    starters.push({
      icon: "📐",
      badge: "Breakthrough Win",
      theme: "orange",
      prompt: `"${first} achieved ${win.level_name} in ${win.objective_statement} this week! Ask: 'How did you solve that tricky question in ${win.objective_code}?'"`,
    });
  } else {
    starters.push({
      icon: "📐",
      badge: "Maths Breakthrough",
      theme: "orange",
      prompt: `"${first} practiced tricky algebraic questions independently today. Ask: 'What was the most interesting puzzle you solved today?'"`,
    });
  }

  if (o?.summary.focus && o.summary.focus.length > 0) {
    const foc = o.summary.focus[0];
    starters.push({
      icon: "🌍",
      badge: "Curiosity Spark",
      theme: "emerald",
      prompt: `"She spent time exploring ${foc.label}. Ask: 'If you were explaining that concept to a friend, what real-world example would you use?'"`,
    });
  } else {
    starters.push({
      icon: "🌍",
      badge: "Sociology Curiosity",
      theme: "emerald",
      prompt: `"She analyzed sociological research methods. Ask: 'If you were studying a group that didn't trust outsiders, how would you gain their trust?'"`,
    });
  }

  function shareWhatsApp() {
    const text = `☀️ ${first}'s Scholr Weekly Update: ${secure}/${totalTopics} topics secure, ${m ? m.totals.active_days : "several"} days studied this month! Great progress!`;
    if (navigator.share) {
      navigator.share({ title: `${first}'s Weekly Learning Sunshine`, text }).catch(() => undefined);
    } else {
      window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`, "_blank");
    }
  }

  return (
    <div className="space-y-6">
      {/* Guardian Executive Overview Header */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 md:p-8 text-white shadow-xl">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-5">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/15 px-3 py-1 font-mono text-xs font-bold text-emerald-300">
              <span>PARENT OVERVIEW</span>
              <span>·</span>
              <span>CAMBRIDGE CIE &amp; IIT FOUNDATION</span>
            </div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              {first}&apos;s Academic Standing &amp; Weekly Digest
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-2xl leading-relaxed">
              Syllabus mastery, independent problem-solving, workload balance and learning notes.
            </p>
          </div>

          <button
            onClick={shareWhatsApp}
            className="px-4 py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 rounded-xl font-extrabold text-xs shadow-lg shadow-emerald-500/20 flex items-center gap-2 transition cursor-pointer flex-none"
          >
            <span>💬</span>
            <span>Share Weekly Digest on WhatsApp</span>
          </button>
        </div>
      </div>

      {/* Dinner Table Conversation Starters */}
      <DinnerStartersCard studentName={first} starters={starters} />

      {overview.error ? <ErrorNote error={overview.error} /> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-5">
          <Card
            title={`How ${first} is doing`}
            subtitle={m ? `This month, next to last month` : undefined}
            action={{ href: "/parent/summary", label: "Open monthly summary" }}
          >
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Tile
                question="Is learning improving?"
                value={String(secure)}
                unit={`of ${totalTopics} topics`}
                note={secureDelta === null ? undefined : `${secureDelta >= 0 ? "+" : ""}${secureDelta} in 8 weeks`}
                tone={secureDelta && secureDelta > 0 ? "good" : "muted"}
              />
              <Tile
                question="Becoming independent?"
                value={percent(independentNow)}
                unit="unassisted"
                note={independentThen === null || independentThen === undefined ? undefined : `Was ${percent(independentThen)} 8 weeks ago`}
                tone={independentNow !== null && independentThen !== null && independentThen !== undefined && independentNow >= independentThen ? "good" : "muted"}
              />
              <Tile
                question="Studying consistently?"
                value={m ? String(m.totals.active_days) : "—"}
                unit={m ? `of ${m.days_counted} days` : undefined}
                note={m ? `Last month: ${m.previous.active_days} days` : undefined}
              />
              <Tile question="Is workload balanced?" value={load.value} note={load.note} />
            </div>
          </Card>

        <Card title="Learning progress" subtitle="Weekly, last 8 weeks" action={{ href: "/parent/summary", label: "Monthly summary" }}>
          {trends.error ? <ErrorNote error={trends.error} /> : null}
          {t && (
            <>
              <div className="grid gap-6 md:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <div className="text-xs font-semibold text-ink">Topics secure</div>
                  <div className="text-[10px] text-muted">Topics at competent or above</div>
                  <TrendLine
                    points={weeks.map((w) => w.topics_secure)}
                    labels={labels}
                    format={(v) => String(Math.round(v))}
                    max={Math.max(totalTopics || 1, ...weeks.map((w) => w.topics_secure ?? 0))}
                    ariaLabel="Topics secure"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <div className="text-xs font-semibold text-ink">Solved without help</div>
                  <div className="text-[10px] text-muted">Share of marked answers with no hints or worked solution</div>
                  <TrendLine
                    points={weeks.map((w) => (w.independent_share === null ? null : w.independent_share * 100))}
                    labels={labels}
                    format={(v) => `${Math.round(v)}%`}
                    max={100}
                    ariaLabel="Solved without help"
                  />
                </div>
              </div>
              <p className="text-[10px] text-muted">Based on marked work, not time spent in the app. Weeks with no marked answers are left out of the share.</p>
            </>
          )}
        </Card>

        <Card title="Strengths & gaps" action={{ href: "/parent/summary", label: "View all" }}>
          {o && (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <div className="text-xs font-bold text-good">Going well</div>
                {o.summary.recent_wins.length === 0 && <p className="text-xs text-muted">No new wins yet this week.</p>}
                {o.summary.recent_wins.map((w) => (
                  <div key={w.objective_code} className="flex items-center gap-2 rounded-xl border border-line-soft px-3 py-2 text-xs">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-ink">{w.objective_statement}</span>
                      <span className="block text-[11px] text-muted">{w.objective_code} · reached this week</span>
                    </span>
                    <Chip tone="brand">{w.level_name}</Chip>
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-2">
                <div className="text-xs font-bold text-warn">Needs support</div>
                {o.summary.focus.length === 0 && <p className="text-xs text-muted">Nothing flagged.</p>}
                {o.summary.focus.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-xl border border-line-soft px-3 py-2 text-xs">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold text-ink">{f.label}</span>
                      <span className="block text-[11px] text-muted">
                        {f.objective_code ? `${f.objective_code} · ` : ""}
                        {f.kind === "mistake" ? "Same mistake more than once" : "Not practised for a while"}
                      </span>
                    </span>
                    <Chip tone="warn">{f.kind === "mistake" ? "Recurring" : "Review due"}</Chip>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        {o?.upcoming_assessments && (
          <Card title="Upcoming assessments" action={{ href: "/parent/schedule", label: "Edit" }}>
            {o.upcoming_assessments.length === 0 && <Empty>None in the next two weeks.</Empty>}
            {o.upcoming_assessments.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-left text-xs">
                  <thead className="text-[10px] uppercase tracking-wide text-faint">
                    <tr>
                      <th className="pb-2 pr-3 font-semibold">Assessment</th>
                      <th className="pb-2 pr-3 font-semibold">When</th>
                      <th className="pb-2 pr-3 font-semibold">Readiness</th>
                      <th className="pb-2 font-semibold">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {o.upcoming_assessments.map((u) => (
                      <tr key={`${u.title}${u.due_at}`} className="border-t border-line-soft">
                        <td className="py-2 pr-3">
                          <span className="block font-semibold text-ink">{u.title}</span>
                          <span className="block text-[11px] text-muted">{u.subject_name}</span>
                        </td>
                        <td className="py-2 pr-3 text-ink-2">{dateTime(u.due_at)}</td>
                        <td className="py-2 pr-3 text-ink-2">
                          {u.objectives_total === 0
                            ? "Topics not listed"
                            : u.objectives_secure === null
                              ? `${u.objectives_total} topics`
                              : `${u.objectives_secure} of ${u.objectives_total} topics secure`}
                        </td>
                        <td className="py-2 text-muted">{u.notes ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        )}

        {plan.data && (
          <Card title="Today's plan" subtitle="Read-only. Only the student marks items done.">
            <DayTimeline plan={plan.data} readOnly />
          </Card>
        )}
      </div>

      <div className="flex flex-col gap-5">
        <WorkloadGuardrail dailyMinutes={Math.round(perDay) || 45} status={load.value} />

        {t && (
          <Card title="Study time" subtitle={`This week · ${minutes(t.days.reduce((n, d) => n + d.study_minutes, 0))}`}>
            <DayBars days={t.days} plannedPerDay={t.planned_minutes_per_day} />
            <div className="flex flex-col gap-1.5">
              {t.subjects.map((s) => (
                <div key={s.subject_id} className="flex items-center justify-between text-xs">
                  <span className="text-ink-2">{s.subject_name}</span>
                  <span className="font-semibold text-ink">{minutes(s.study_minutes)}</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {t && (
          <Card title="Help needed" subtitle="How answers were reached, by week">
            <HelpMixBars weeks={weeks} labels={labels} />
          </Card>
        )}

        {o && (
          <Card title="How you can help" subtitle="From this month's learning">
            <ul className="flex flex-col gap-2">
              {o.suggestions.map((sug, i) => (
                <li key={i} className="rounded-xl border border-line-soft px-3 py-2 text-xs">
                  <span className="font-bold text-ink">{sug.lead}: </span>
                  <span className="text-ink-2">{sug.text}</span>
                </li>
              ))}
            </ul>
            <p className="text-[10px] text-muted">Based on marked work, mistakes and plans. No AI writes this.</p>
          </Card>
        )}

        {external.data && external.data.subjects.length > 0 && (
          <Card
            title="IIT Foundation"
            subtitle="Last 4 weeks. Learning that happens outside Scholr."
            action={{ href: "/parent/iit", label: "Open" }}
          >
            <ul className="flex flex-col gap-1.5">
              {external.data.subjects.map((s) => (
                <li key={s.subject_id} className="flex items-baseline justify-between gap-2 text-xs">
                  <span className="min-w-0 truncate text-ink-2">{s.subject_name.replace("IIT Foundation ", "")}</span>
                  <span className="font-semibold text-ink">
                    {s.sessions} session{s.sessions === 1 ? "" : "s"}
                    {s.accuracy !== null ? ` · ${Math.round(s.accuracy * 100)}%` : ""}
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-[11px] text-muted">
              {external.data.reinforcement.length === 0
                ? "Nothing from these classes needs IGCSE follow-up right now."
                : `${external.data.reinforcement.length} IGCSE topic(s) would make the next class easier.`}
            </p>
          </Card>
        )}

        {o?.evaluations_needing_review !== null && o && (
          <Card title="Marks to check" action={{ href: "/parent/review", label: "Review" }}>
            <p className="text-sm text-ink-2">
              {o.evaluations_needing_review === 0 ? "Nothing waiting." : `${o.evaluations_needing_review} answer(s) the AI was not sure about.`}
            </p>
          </Card>
        )}

        {o?.safety && (
          <Card title="Safety">
            {o.safety.open_total === 0 ? (
              <p className="text-sm text-good">No open safety alerts. You are told straight away if anything needs attention.</p>
            ) : (
              <Link href="/parent/safety" className="text-sm font-semibold text-alert">
                {o.safety.open_total} open alert(s) — view
              </Link>
            )}
          </Card>
        )}

        {o && (
          <Card title={`${first} can see what you can see`} action={{ href: "/consent", label: "Manage" }}>
            <p className="text-xs text-muted">Your access: {o.scopes.join(", ")}.</p>
          </Card>
        )}
      </div>
    </div>
  </div>
  );
}
