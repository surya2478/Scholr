"use client";

import Link from "next/link";
import { useMe } from "@/components/AppShell";
import { DayTimeline } from "@/components/DayTimeline";
import { Icon, type IconName } from "@/components/icons";
import { StreamSection } from "@/components/learn/Streams";
import { SubjectLevels } from "@/components/SubjectLevels";
import { Card, Chip, Empty, ErrorNote } from "@/components/ui";
import type { DailyPractice, Plan, ProgressSummary, Stream, UpcomingBrief } from "@/lib/api";
import { dateTime, greeting, minutes, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";

function DayStat({
  label,
  value,
  tint,
  ink,
  icon,
}: {
  label: string;
  value: string;
  tint: string;
  ink: string;
  icon: IconName;
}) {
  return (
    <div className="flex min-h-[64px] items-center gap-3 rounded-2xl bg-[#FFFDF9] border border-amber-200/70 p-3 shadow-2xs">
      <span
        className="flex h-[38px] w-[38px] flex-none items-center justify-center rounded-2xl shadow-xs"
        style={{ background: tint, color: ink }}
      >
        <Icon name={icon} className="h-[19px] w-[19px]" />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-[11px] font-semibold leading-tight text-slate-500">{label}</span>
        <span className="text-sm font-fun font-bold leading-tight text-slate-900 mt-0.5">{value}</span>
      </span>
    </div>
  );
}

export default function StudentHome() {
  const me = useMe();
  const plan = useApi<Plan>("/plan/today");
  const progress = useApi<ProgressSummary>("/progress/summary");
  const upcoming = useApi<UpcomingBrief[]>("/upcoming-assessments");
  const streams = useApi<Stream[]>("/learn/streams");
  const daily = useApi<DailyPractice>("/practice/daily");

  const first = me?.student?.display_name.split(" ")[0] ?? "";
  const items = plan.data?.items ?? [];
  const done = items.filter((i) => i.status === "completed").length;
  const week = progress.data?.week;
  const subjects = progress.data?.subjects ?? [];
  const secure = subjects.reduce((n, s) => n + s.competent_or_better, 0);
  const totalTopics = subjects.reduce((n, s) => n + s.objectives_total, 0);

  // Derive next mission
  const nextItem = items.find((i) => i.status === "planned" || i.status === "in_progress");

  return (
    <div className="space-y-6">
      {/* CuriousJr-Style Hero Greeting Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-amber-100 via-[#FFF4E8] to-orange-50 border-2 border-amber-200/80 p-6 md:p-8 shadow-sm">
        {/* Floating Playful Icons in Background */}
        <div className="absolute -right-4 -bottom-4 text-7xl opacity-20 pointer-events-none select-none animate-float">
          🚀
        </div>
        <div className="absolute left-1/2 -top-6 text-6xl opacity-15 pointer-events-none select-none animate-float-delayed">
          🪐
        </div>
        <div className="absolute right-1/4 top-3 text-4xl opacity-20 pointer-events-none select-none">
          ✏️
        </div>

        <div className="flex flex-col lg:flex-row items-center justify-between gap-6 relative z-10">
          <div className="space-y-2 text-center lg:text-left">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/90 border border-orange-200 text-orange-700 text-xs font-bold shadow-2xs">
              <span>🌈</span>
              <span>{greeting()} Learning Quest</span>
              {plan.data && (
                <>
                  <span className="text-orange-300">•</span>
                  <span>{minutes(plan.data.planned_minutes)} Planned Today</span>
                </>
              )}
            </div>

            <h1 className="text-2xl sm:text-3xl md:text-4xl font-fun font-bold text-slate-900 tracking-tight">
              Ready to learn something amazing,{" "}
              <span className="text-orange-600 underline decoration-wavy decoration-orange-300">
                {first || "Student"}?
              </span>
            </h1>

            <p className="text-sm md:text-base text-slate-600 max-w-xl font-medium">
              You&apos;re doing fantastic! Tackle today&apos;s challenges with Cambridge-verified guidance, step-by-step math checking, and your AI study companion!
            </p>

            <div className="flex flex-wrap items-center justify-center lg:justify-start gap-2 pt-1">
              {me?.student?.enrollments.map((e) => (
                <Chip key={e.subject_id} tone="brand">
                  {e.subject_name}
                </Chip>
              ))}
            </div>
          </div>

          {/* Quick Jump Quest Card */}
          <div className="bg-white/95 backdrop-blur rounded-2xl border-2 border-amber-300 p-4 shadow-md flex items-center gap-4 max-w-md w-full">
            <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-3xl shadow-md text-white flex-none select-none">
              🎯
            </div>
            <div className="flex-1 min-w-0">
              <span className="text-[11px] uppercase font-bold tracking-wider text-orange-600">
                Today&apos;s Quick Mission
              </span>
              <h3 className="text-sm font-fun font-bold text-slate-900 truncate">
                {nextItem ? (nextItem.objective_statement ?? nextItem.subject_name) : "Practice Cambridge Questions"}
              </h3>
              <p className="text-xs text-slate-500 mt-0.5 truncate">
                {nextItem ? `${nextItem.subject_name} · ${nextItem.est_minutes} min · ${nextItem.reason}` : "Step-by-step practice with instant checkmarks"}
              </p>
            </div>
            <Link
              href="/student/practice"
              className="px-4 py-2.5 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-fun font-bold text-sm shadow-md shadow-orange-500/30 transition-all hover:scale-105 active:scale-95 flex-none"
            >
              Let&apos;s Go! →
            </Link>
          </div>
        </div>
      </div>

      {/* Today's practice set (docs/STUDENT-APP.md step 4) */}
      {daily.data && daily.data.total > 0 && (
        <Link
          href="/student/practice/daily"
          className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border-2 border-emerald-200 bg-[#F6FEF9] p-5 shadow-sm transition hover:shadow-md"
        >
          <div>
            <div className="text-lg font-fun font-bold text-slate-900">✅ Today&apos;s practice set</div>
            <div className="text-xs font-medium text-slate-600">
              {daily.data.total} short questions picked for today — from your plan, your mistakes and what&apos;s due.
            </div>
          </div>
          <span className="rounded-full border border-emerald-300 bg-white px-3 py-1 text-sm font-fun font-bold text-emerald-800">
            {daily.data.done === daily.data.total ? "All done 🎉" : `${daily.data.done} of ${daily.data.total} done →`}
          </span>
        </Link>
      )}

      {/* Streams and subjects, from the API (docs/STUDENT-APP.md). Real counts only: no invented progress. */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-fun font-bold text-slate-900 flex items-center gap-2">
              <span>🎒</span>
              <span>Your subjects</span>
            </h2>
            <p className="text-xs text-slate-500 font-medium">Open a subject to read a topic, try its questions and ask the Tutor</p>
          </div>
          <Link
            href="/student/learn"
            className="text-xs font-fun font-bold text-orange-600 bg-orange-100/80 px-3 py-1 rounded-full border border-orange-200"
          >
            All subjects →
          </Link>
        </div>
        {(streams.data ?? []).map((stream) => (
          <StreamSection key={stream.key} stream={stream} />
        ))}
      </div>

      {/* Grid: Left 8 cols (My Day & Quick Actions) + Right 4 cols (Progress & AI Companion) */}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="flex flex-col gap-5">
          {/* My Day Timeline */}
          <Card
            title="My Day Learning Adventure"
            subtitle={plan.data ? shortDate(plan.data.plan_date) : undefined}
          >
            {plan.error ? <ErrorNote error={plan.error} /> : null}
            {plan.data && (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <DayStat
                    label="Study time"
                    value={minutes(plan.data.planned_minutes)}
                    tint="#FFF4E8"
                    ink="#F97316"
                    icon="clock"
                  />
                  <DayStat
                    label="Completed"
                    value={`${done}/${items.length}`}
                    tint="#ECFDF5"
                    ink="#10B981"
                    icon="check"
                  />
                  <DayStat
                    label="Without help"
                    value={week ? `${week.answers_without_help} of ${week.attempts_evaluated}` : "–"}
                    tint="#F0FDFA"
                    ink="#0D9488"
                    icon="spark"
                  />
                  <DayStat
                    label="Mistakes fixed"
                    value={week ? `${week.mistakes_fixed} this week` : "–"}
                    tint="#FDF2F8"
                    ink="#DB2777"
                    icon="repair"
                  />
                </div>
                {plan.data.notices.map((n) => (
                  <p key={n} className="rounded-2xl bg-orange-50 border border-orange-200 px-4 py-2.5 text-xs text-orange-800 font-medium">
                    {n}
                  </p>
                ))}
                <DayTimeline plan={plan.data} onChange={plan.setData} />
              </>
            )}
          </Card>

          {/* Continue Learning Subjects */}
          <Card title="Continue learning" subtitle="Pick up where you left off">
            {subjects.length === 0 && <Empty>Your subjects will appear here.</Empty>}
            <div className="grid gap-3.5 md:grid-cols-2">
              {subjects.map((s) => {
                const share = s.objectives_total ? Math.round((s.competent_or_better / s.objectives_total) * 100) : 0;
                return (
                  <div
                    key={s.subject_id}
                    className="flex flex-col gap-2.5 rounded-2xl border-2 border-amber-200/80 bg-[#FFFDF9] p-4 shadow-2xs hover:border-orange-300 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-fun font-bold text-slate-900">{s.subject_name}</div>
                      <span className="text-xs font-fun font-bold text-orange-600 bg-orange-50 border border-orange-200 px-2.5 py-0.5 rounded-full">
                        {share}%
                      </span>
                    </div>
                    <div className="text-[11.5px] text-slate-500 font-medium">
                      {s.competent_or_better} of {s.objectives_total} topics secure
                      {s.open_mistakes > 0 ? ` · ${s.open_mistakes} mistake${s.open_mistakes === 1 ? "" : "s"} to fix` : ""}
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-orange-400 to-amber-500 transition-all"
                        style={{ width: `${share}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-end pt-1">
                      <Link
                        href={`/student/practice?subject=${s.subject_id}`}
                        className="text-xs font-fun font-bold text-orange-600 hover:text-orange-700 flex items-center gap-1"
                      >
                        <span>Continue Practice</span>
                        <span>→</span>
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>

          {/* Quick Actions */}
          <Card title="Quick actions" subtitle="Shortcuts for quick practice and reviews">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { href: "/student/tutor", label: "Ask my AI", hint: "Instant help 🦉", icon: "tutor" as IconName, emoji: "🦉" },
                { href: "/student/practice", label: "Practise questions", hint: "Sharpen skills 📐", icon: "practice" as IconName, emoji: "✏️" },
                { href: "/student/mistakes", label: "My mistakes", hint: "Learn & improve", icon: "mistakes" as IconName, emoji: "🔍" },
                { href: "/student/tests", label: "My tests", hint: "Baselines & quizzes", icon: "tests" as IconName, emoji: "📝" },
              ].map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  className="flex items-center gap-3 rounded-2xl border-2 border-amber-200/70 bg-[#FFFDF9] p-3 hover:bg-orange-50/50 hover:border-orange-300 transition-all hover:scale-102"
                >
                  <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-orange-100 text-lg">
                    {a.emoji}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-fun font-bold text-slate-900">{a.label}</span>
                    <span className="block truncate text-[11px] text-slate-400 font-medium">{a.hint}</span>
                  </span>
                </Link>
              ))}
            </div>
          </Card>
        </div>

        {/* Right Sidebar Column */}
        <div className="flex flex-col gap-5">
          {/* Progress Card */}
          <Card title="Your progress" action={{ href: "/student/progress", label: "View details" }}>
            {progress.error ? <ErrorNote error={progress.error} /> : null}
            <div className="grid grid-cols-2 gap-3">
              <DayStat
                label="Topics secure"
                value={`${secure}/${totalTopics}`}
                tint="#FFF4E8"
                ink="#F97316"
                icon="flag"
              />
              <DayStat
                label="Studied this week"
                value={week ? minutes(week.study_minutes) : "–"}
                tint="#ECFDF5"
                ink="#10B981"
                icon="clock"
              />
              <DayStat
                label="Active days"
                value={week ? `${week.active_days} of 7` : "–"}
                tint="#F0FDFA"
                ink="#0D9488"
                icon="calendar"
              />
              <DayStat
                label="Answers marked"
                value={week ? String(week.attempts_evaluated) : "–"}
                tint="#FDF2F8"
                ink="#DB2777"
                icon="check"
              />
            </div>
          </Card>

          {/* Subject Mastery Levels */}
          <Card title="Subject mastery" action={{ href: "/student/progress", label: "View all" }}>
            <div className="space-y-3">
              {subjects.map((s) => (
                <SubjectLevels key={s.subject_id} subject={s} />
              ))}
            </div>
          </Card>

          {/* Upcoming Tests */}
          {upcoming.data && (
            <Card title="Upcoming" action={{ href: "/student/tests", label: "View all" }}>
              {upcoming.data.length === 0 && <Empty>Nothing booked in the next weeks.</Empty>}
              <ul className="flex flex-col gap-2">
                {upcoming.data.slice(0, 4).map((u) => (
                  <li
                    key={`${u.title}${u.due_at}`}
                    className="flex items-center gap-2 rounded-2xl border border-amber-200/70 bg-[#FFFDF9] p-3 shadow-2xs"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-bold text-slate-800">{u.title}</span>
                      <span className="block text-[11px] text-slate-400 font-medium">{dateTime(u.due_at)}</span>
                    </span>
                    <Link
                      href={`/student/practice?subject=${u.subject_id}`}
                      className="text-xs font-fun font-bold text-orange-600 hover:text-orange-700 bg-orange-50 px-2.5 py-1 rounded-lg border border-orange-200"
                    >
                      Study
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Focus Next */}
          <Card title="Focus next" subtitle="Targeted review recommended by AI">
            {progress.data && progress.data.focus.length === 0 && (
              <Empty>Nothing urgent. Keep practising at your own pace! 🌟</Empty>
            )}
            <ul className="flex flex-col gap-2">
              {progress.data?.focus.map((f, i) => (
                <li key={i} className="flex items-start gap-2.5 text-xs p-2.5 rounded-2xl bg-[#FFFDF9] border border-amber-200/60">
                  <Chip tone={f.kind === "mistake" ? "warn" : "brand"}>
                    {f.kind === "mistake" ? "Mistake" : "Review"}
                  </Chip>
                  <span className="text-slate-700 font-medium pt-0.5">
                    {f.objective_code ? <b className="font-bold text-slate-900">{f.objective_code} </b> : null}
                    {f.label}
                  </span>
                </li>
              ))}
            </ul>
          </Card>

          {/* AI Companion Card with Mascot */}
          <section className="rounded-3xl border-2 border-amber-300 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-5 shadow-sm space-y-3">
            <div className="flex items-center gap-3">
              <div className="h-12 w-12 rounded-2xl bg-white border border-amber-200 flex items-center justify-center text-3xl shadow-sm">
                🦉
              </div>
              <div>
                <h3 className="text-base font-fun font-bold text-slate-900">Your Tutor</h3>
                <p className="text-xs text-slate-500 font-medium">Cambridge study support, anytime</p>
              </div>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed font-medium">
              Stuck or stressed about studying? Let&apos;s break it down into small, doable steps together.
            </p>
            <Link
              href="/student/tutor"
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-fun font-bold text-sm shadow-md shadow-orange-500/20 transition-all hover:scale-102 active:scale-98"
            >
              <span>Chat with Study Buddy</span>
              <span>→</span>
            </Link>
          </section>
        </div>
      </div>
    </div>
  );
}
