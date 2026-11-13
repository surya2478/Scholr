"use client";

import Link from "next/link";
import { useMe } from "@/components/AppShell";
import { DayTimeline } from "@/components/DayTimeline";
import { Icon, type IconName } from "@/components/icons";
import { SessionDoors } from "@/components/learn/SessionDoors";
import { StreamSection } from "@/components/learn/Streams";
import { SubjectLevels } from "@/components/SubjectLevels";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { Commitment, DailyPractice, Plan, ProgressSummary, Stream, UpcomingBrief } from "@/lib/api";
import { commitmentDays, greeting, minutes, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

// Home answers five questions, in this order, and nothing else (PRINCIPLES §UX):
//   What should I do today? · Why does it matter? · How am I progressing? · What am I struggling with? · What next?
// Every number on this page comes from her own record. No points, no levels, no streaks, no badges: the reason to
// come back is that the work is clear and worth doing, not that a counter would break.

/** A time of day, as the planner stores it ("16:30:00"), in the form she reads. */
function clock(value: string | null) {
  return value ? value.slice(0, 5) : "";
}

/**
 * The one thing to do now: a day with no room leads with that, then her plan, then today's set, then the
 * subjects she can open.
 *
 * On a full evening the card does not push work (`primary: false`): her availability on Monday and Thursday is
 * taken entirely by the IIT class, and the family's decision (D-E9, 26 Oct 2026) is that those evenings really
 * are full. The set is still there, offered quietly underneath, because it is her own queue rather than
 * something the day has scheduled.
 */
function nextAction(plan: Plan | null, daily: DailyPractice | null) {
  const left = daily ? daily.total - daily.done : 0;
  if (plan && plan.capacity_minutes === 0) {
    const classes = plan.timeline.filter((b) => b.kind === "commitment");
    return {
      kind: "quiet" as const,
      title: classes.length > 0 ? "Today is full." : "No study time today.",
      detail:
        classes.length > 0
          ? `${classes.map((c) => [c.title, clock(c.start)].filter(Boolean).join(" at ")).join(" · ")}. Scholr has nothing scheduled today — that's the plan, not a gap.`
          : "Nothing is scheduled today. A rest day is a rest day.",
      minutes: 0,
      href: "/student/practice/daily",
      cta: left > 0 ? `If you do want something: today's set, ${left} question${left === 1 ? "" : "s"}` : "",
      primary: false,
    };
  }
  const item = plan?.items.find((i) => i.status === "planned" || i.status === "in_progress");
  if (item) {
    return {
      kind: "plan" as const,
      title: item.objective_statement ?? item.subject_name,
      detail: `${item.subject_name} · ${item.reason}`,
      minutes: item.est_minutes,
      href: item.objective_id
        ? `/student/learn/topic/${item.objective_id}`
        : `/student/practice?subject=${item.subject_id}`,
      cta: "Start this",
      primary: true,
    };
  }
  if (left > 0) {
    return {
      kind: "set" as const,
      title: `Today's set — ${left} question${left === 1 ? "" : "s"} left`,
      detail: "Chosen from your plan, your mistakes and what's due for revision.",
      minutes: daily?.doors.find((d) => d.key === "today")?.minutes ?? 0,
      href: "/student/practice/daily",
      cta: "Open today's set",
      primary: true,
    };
  }
  if (daily && daily.total > 0) {
    return {
      kind: "done" as const,
      title: "That's today's work done.",
      detail:
        daily.tomorrow.length > 0
          ? `Tomorrow starts with ${daily.tomorrow[0].objective_code} ${daily.tomorrow[0].objective_statement}.`
          : "Nothing is waiting for tomorrow yet.",
      minutes: 0,
      href: "/student/practice/daily",
      cta: "See what you did",
      primary: true,
    };
  }
  return {
    kind: "open" as const,
    title: "Pick up where you like",
    detail: "Open a subject and choose a topic — your lessons and questions are all there.",
    minutes: 0,
    href: "/student/learn",
    cta: "Open my subjects",
  };
}

function WeekFact({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-lg font-fun font-bold text-ink">{value}</span>
      <span className="text-[11px] font-medium text-muted">{label}</span>
    </div>
  );
}

function QuickLink({ href, label, icon }: { href: string; label: string; icon: IconName }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 rounded-xl border border-line-soft bg-white px-3 py-2 text-xs font-semibold text-ink-2 transition hover:border-brand hover:text-brand"
    >
      <Icon name={icon} className="h-4 w-4" />
      {label}
    </Link>
  );
}

export default function StudentHome() {
  const me = useMe();
  const plan = useApi<Plan>("/plan/today");
  const progress = useApi<ProgressSummary>("/progress/summary");
  const upcoming = useApi<UpcomingBrief[]>("/upcoming-assessments?upcoming_only=true");
  const streams = useApi<Stream[]>("/learn/streams");
  const daily = useApi<DailyPractice>("/practice/daily");
  const commitments = useApi<Commitment[]>("/commitments");

  const first = me?.student?.display_name.split(" ")[0] ?? "";
  const week = progress.data?.week;
  const subjects = progress.data?.subjects ?? [];
  const focus = progress.data?.focus ?? [];
  const wins = progress.data?.recent_wins ?? [];
  const next = nextAction(plan.data ?? null, daily.data ?? null);
  const soon = (upcoming.data ?? []).slice(0, 2);

  return (
    <div className="space-y-7">
      {/* ---- Who, and what today is ------------------------------------------------------------------ */}
      <header className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl md:text-3xl font-fun font-bold tracking-tight text-ink">
            {greeting()}
            {first ? `, ${first}` : ""}.
          </h1>
          <p className="mt-0.5 text-sm font-medium text-muted">
            {plan.data ? shortDate(plan.data.plan_date) : "Today"}
            {plan.data && plan.data.planned_minutes > 0 ? ` · ${minutes(plan.data.planned_minutes)} planned` : ""}
          </p>
        </div>
        {soon.length > 0 && (
          <p className="text-xs font-medium text-muted">
            Coming up: <span className="font-bold text-ink-2">{soon[0].title}</span>
            {soon.length > 1 ? ` and ${soon.length - 1} more` : ""} ·{" "}
            <Link href="/student/tests" className="font-bold text-brand hover:underline">
              see all
            </Link>
          </p>
        )}
      </header>

      {/* ---- 1. What should I do today, and why does it matter? --------------------------------------- */}
      <section className="rounded-3xl border border-line bg-white p-6 shadow-xs md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand">
              {next.kind === "plan" || next.kind === "set" ? "Do this next" : "Today"}
            </span>
            <h2 className="mt-1 text-xl font-fun font-bold leading-snug text-ink md:text-2xl">{next.title}</h2>
            <p className="mt-1 text-sm font-medium text-muted">{next.detail}</p>
          </div>
          {next.minutes > 0 && (
            <span className="rounded-xl border border-brand-soft bg-brand-soft px-3 py-1.5 text-xs font-bold text-brand">
              about {next.minutes} min
            </span>
          )}
        </div>

        {plan.error ? <ErrorNote error={plan.error} /> : null}

        <div className="mt-5 flex flex-wrap items-center gap-2.5">
          {next.primary ? (
            <Link
              href={next.href}
              className="inline-flex h-11 items-center rounded-xl bg-brand px-5 text-sm font-bold text-white shadow-sm transition hover:bg-brand-strong"
            >
              {next.cta} →
            </Link>
          ) : next.cta ? (
            <Link href={next.href} className="text-sm font-semibold text-brand hover:underline">
              {next.cta} →
            </Link>
          ) : null}
          <Link
            href="/student/homework"
            className="inline-flex h-11 items-center gap-2 rounded-xl border border-line bg-white px-4 text-sm font-semibold text-ink-2 transition hover:border-brand hover:text-brand"
          >
            <Icon name="notes" className="h-4 w-4" />
            Photograph my homework
          </Link>
          <Link
            href="/student/tutor"
            className="inline-flex h-11 items-center gap-2 rounded-xl border border-line bg-white px-4 text-sm font-semibold text-ink-2 transition hover:border-brand hover:text-brand"
          >
            <Icon name="tutor" className="h-4 w-4" />
            Ask the Tutor
          </Link>
        </div>
      </section>

      {/* ---- How much time have you got? (the three doors, F2) ---------------------------------------- */}
      <SessionDoors doors={daily.data?.doors ?? []} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-6">
          {/* ---- 2. What am I struggling with? ------------------------------------------------------- */}
          <Card
            title="Worth your attention"
            subtitle="Mistakes you have not cleared, and topics going quiet."
            action={{ href: "/student/mistakes", label: "All mistakes" }}
          >
            {progress.error ? <ErrorNote error={progress.error} /> : null}
            {progress.data && focus.length === 0 && (
              <Empty>Nothing is nagging right now — no open mistakes, nothing overdue for revision.</Empty>
            )}
            <ul className="flex flex-col gap-2">
              {focus.slice(0, 5).map((f, i) => (
                <li key={i}>
                  <Link
                    href={f.objective_id ? `/student/learn/topic/${f.objective_id}` : "/student/mistakes"}
                    className="flex items-start gap-2.5 rounded-xl border border-line-soft bg-tile p-3 transition hover:border-brand"
                  >
                    <Chip tone={f.kind === "mistake" ? "warn" : "brand"}>
                      {f.kind === "mistake" ? "Mistake" : "Revision"}
                    </Chip>
                    <span className="pt-0.5 text-xs font-medium text-ink-2">
                      {f.objective_code ? <b className="font-bold text-ink">{f.objective_code} </b> : null}
                      {f.label}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Card>

          {/* ---- 3. What's the shape of my day? ------------------------------------------------------ */}
          <Card title="Today's plan" subtitle={plan.data ? shortDate(plan.data.plan_date) : undefined}>
            {plan.data?.notices.map((n) => (
              <p key={n} className="rounded-xl border border-brand-soft bg-brand-soft px-4 py-2.5 text-xs font-medium text-ink-2">
                {n}
              </p>
            ))}
            {plan.data ? <DayTimeline plan={plan.data} onChange={plan.setData} /> : null}
            {commitments.data && commitments.data.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 border-t border-line-soft pt-3">
                <span className="text-[11px] font-bold uppercase tracking-wider text-faint">This week</span>
                {commitments.data.map((c) => (
                  <span key={c.id} className="rounded-lg border border-line-soft bg-tile px-2.5 py-1 text-[11px] font-medium text-ink-2">
                    {[commitmentDays(c.rrule), c.title, c.start_time].filter(Boolean).join(" · ")}
                  </span>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* ---- 5. How am I progressing? -------------------------------------------------------------- */}
        <aside className="flex flex-col gap-6">
          <Card title="Your week" subtitle={week ? `Since ${shortDate(week.since)}` : undefined}>
            {week ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <WeekFact value={`${week.active_days} of 7`} label="days you studied" />
                  <WeekFact value={minutes(week.study_minutes)} label="spent answering" />
                  <WeekFact
                    value={week.attempts_evaluated > 0 ? `${week.answers_without_help}/${week.attempts_evaluated}` : "—"}
                    label="solved without help"
                  />
                  <WeekFact value={`${week.mistakes_fixed}`} label="mistakes cleared" />
                </div>
                <p className="text-[11px] font-medium text-faint">
                  A rest day is a rest day. Nothing here is a streak to keep up.
                </p>
              </>
            ) : (
              <Empty>Your week will fill in as you work.</Empty>
            )}
          </Card>

          <Card title="Topics secure" subtitle="Counted from questions you have answered — never from reading alone.">
            {subjects.length === 0 && <Empty>Your subjects will appear here.</Empty>}
            <div className="flex flex-col gap-4">
              {subjects.map((s) => (
                <SubjectLevels key={s.subject_id} subject={s} />
              ))}
            </div>
          </Card>

          {wins.length > 0 && (
            <Card title="Recently secure" subtitle="Topics you have proved, not just read.">
              <ul className="flex flex-col gap-1.5">
                {wins.slice(0, 4).map((w) => (
                  <li key={w.objective_code} className="text-xs font-medium text-ink-2">
                    <b className="font-bold text-ink">{w.objective_code}</b> {w.objective_statement}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <div className="flex flex-wrap gap-2">
            <QuickLink href="/student/practice" label="Question bank" icon="practice" />
            <QuickLink href="/student/papers" label="Past papers" icon="clock" />
            <QuickLink href="/student/mistakes" label="My mistakes" icon="mistakes" />
            <QuickLink href="/student/progress" label="Progress" icon="progress" />
            <QuickLink href="/student/iit" label="IIT classes" icon="external" />
          </div>
        </aside>
      </div>

      {/* ---- 4. What next? Everything she can open ------------------------------------------------- */}
      <section className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <h2 className="text-lg font-fun font-bold text-ink">Your subjects</h2>
            <p className="text-xs font-medium text-muted">Every topic, with its lesson and its questions.</p>
          </div>
          <Link href="/student/learn" className="text-xs font-bold text-brand hover:underline">
            See all topics →
          </Link>
        </div>
        {streams.error ? <ErrorNote error={streams.error} /> : null}
        {(streams.data ?? []).map((stream) => (
          <StreamSection key={stream.key} stream={stream} />
        ))}
      </section>
    </div>
  );
}
