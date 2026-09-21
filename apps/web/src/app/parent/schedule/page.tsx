"use client";

import { useEffect, useState } from "react";
import { Button, Card, Empty, ErrorNote } from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, minutes } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

type Commitment = { id: string; kind: string; title: string; rrule: string; start_time: string | null; duration_min: number };
type Upcoming = { id: string; subject_id: string; title: string; due_at: string };
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];

type TopicNode = { id: string; code: string; name: string; depth: number; children: TopicNode[] };
type TeachingEntry = { id: string; subject_id: string; term: string; label: string; starts_on: string | null; ends_on: string | null; topic_ids: string[] };

function flatten(nodes: TopicNode[], out: TopicNode[] = []): TopicNode[] {
  for (const n of nodes) {
    out.push(n);
    flatten(n.children, out);
  }
  return out;
}

// What the school is teaching now: the planner schedules these topics as "school topic" work (ARCHITECTURE §16).
function TeachingPlan({ query, subjects, onError }: {
  query: string;
  subjects: { subject_id: string; subject_name: string }[];
  onError: (e: unknown) => void;
}) {
  const entries = useApi<TeachingEntry[]>(query ? `/teaching-plan?${query}` : null);
  const [subjectId, setSubjectId] = useState("");
  const tree = useApi<{ topics: TopicNode[] }>(subjectId ? `/subjects/${subjectId}/tree` : null);
  const [form, setForm] = useState({ term: "Term 1", label: "", starts_on: "", ends_on: "", topic_ids: [] as string[] });
  const topics = tree.data ? flatten(tree.data.topics) : [];
  const names = Object.fromEntries(subjects.map((s) => [s.subject_id, s.subject_name]));

  async function add() {
    try {
      await api(`/teaching-plan?${query}`, {
        method: "POST",
        json: { subject_id: subjectId, term: form.term, label: form.label, starts_on: form.starts_on || null, ends_on: form.ends_on || null, topic_ids: form.topic_ids },
      });
      setForm({ ...form, label: "", topic_ids: [] });
      await entries.reload();
    } catch (err) {
      onError(err);
    }
  }

  return (
    <Card
      title="🏫 School Teaching Plan"
      subtitle="Which topics the class is covering right now. Scholr syncs practice with school so she never feels split."
    >
      {entries.data?.length === 0 && (
        <Empty>No school teaching plan entries added yet.</Empty>
      )}
      <ul className="flex flex-col gap-2.5">
        {entries.data?.map((e) => (
          <li key={e.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line-soft bg-white/80 p-3.5 shadow-xs transition hover:border-brand/40">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-purple-600 font-fun font-bold text-sm">
              📚
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <b className="font-bold text-ink">{e.label}</b>
                <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand-strong">
                  {names[e.subject_id] ?? "Subject"}
                </span>
                <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700">
                  {e.term}
                </span>
              </div>
              <div className="mt-0.5 text-xs text-muted">
                📅 {e.starts_on ?? "Ongoing"} to {e.ends_on ?? "End of term"} · 🎯 {e.topic_ids.length} syllabus topic(s) selected
              </div>
            </div>
            <button
              className="rounded-lg px-2.5 py-1 text-xs font-semibold text-alert hover:bg-rose-50 transition"
              onClick={async () => {
                try {
                  await api(`/teaching-plan/${e.id}`, { method: "DELETE" });
                  await entries.reload();
                } catch (err) {
                  onError(err);
                }
              }}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>

      <div className="flex flex-col gap-3 rounded-2xl border border-line-soft bg-gradient-to-b from-[#FFFDF9] to-[#F7F3EB] p-4">
        <h4 className="font-fun font-bold text-sm text-ink flex items-center gap-1.5">
          <span>➕</span> Add a New School Unit
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
          <select
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          >
            <option value="">Select Subject</option>
            {subjects.map((s) => (
              <option key={s.subject_id} value={s.subject_id}>
                {s.subject_name}
              </option>
            ))}
          </select>
          <input
            placeholder="Unit label (e.g. Unit 3 Trigonometry)"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
          <input
            placeholder="Term (e.g. Term 1)"
            value={form.term}
            onChange={(e) => setForm({ ...form, term: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
          <div className="grid grid-cols-2 gap-1.5">
            <input
              type="date"
              title="Start date"
              value={form.starts_on}
              onChange={(e) => setForm({ ...form, starts_on: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-2 text-[11px] font-medium text-ink focus:border-brand focus:outline-none"
            />
            <input
              type="date"
              title="End date"
              value={form.ends_on}
              onChange={(e) => setForm({ ...form, ends_on: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-2 text-[11px] font-medium text-ink focus:border-brand focus:outline-none"
            />
          </div>
        </div>

        {topics.length > 0 && (
          <div className="flex flex-col gap-1.5 pt-1">
            <span className="text-[11px] font-bold text-ink-2">
              Select syllabus topics covered in this unit ({form.topic_ids.length} selected):
            </span>
            <div className="flex max-h-48 flex-wrap gap-1.5 overflow-y-auto rounded-xl border border-line-soft bg-white/70 p-2.5">
              {topics.map((t) => {
                const on = form.topic_ids.includes(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setForm({ ...form, topic_ids: on ? form.topic_ids.filter((x) => x !== t.id) : [...form.topic_ids, t.id] })}
                    className={`rounded-full border px-3 py-1 text-xs transition ${
                      on
                        ? "border-brand bg-brand font-bold text-white shadow-xs"
                        : "border-line bg-white text-ink hover:border-brand/40"
                    } ${t.depth === 0 ? "font-bold" : ""}`}
                  >
                    {t.code} {t.name}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        <div className="flex justify-end pt-1">
          <Button disabled={!subjectId || !form.label || form.topic_ids.length === 0} onClick={add}>
            Save to Teaching Plan
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function Schedule() {
  const { id, query, subjects } = useLinkedStudent();
  const availability = useApi<{ minutes: number[] }>(id ? `/students/${id}/availability` : null);
  const commitments = useApi<Commitment[]>(id ? `/commitments?${query}` : null);
  const upcoming = useApi<Upcoming[]>(id ? `/upcoming-assessments?${query}` : null);
  const [week, setWeek] = useState<number[]>([0, 0, 0, 0, 0, 0, 0]);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [commit, setCommit] = useState({ title: "", kind: "iit_class", days: [] as string[], start_time: "17:00", duration_min: 60 });
  const [test, setTest] = useState({ title: "", subject_id: "", due_at: "" });

  useEffect(() => {
    if (availability.data) setWeek(availability.data.minutes);
  }, [availability.data]);

  async function run(fn: () => Promise<unknown>) {
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err);
    }
  }

  const totalWeeklyMinutes = week.reduce((a, b) => a + b, 0);
  const totalWeeklyHours = (totalWeeklyMinutes / 60).toFixed(1);

  return (
    <div className="flex flex-col gap-6">
      {/* Friendly banner */}
      <section className="relative overflow-hidden rounded-3xl border border-[#FFE8CD] bg-gradient-to-r from-[#FFF5EB] via-[#FFF9F2] to-[#EEF5FC] p-6 shadow-sm">
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-amber-800 shadow-xs">
              <span>📅</span> Balanced Timetable
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              Schedule & Commitments
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Set available study time and block out coaching, school, or sports so Scholr builds realistic daily plans with a guaranteed 15% rest buffer.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-amber-200/60 bg-white/80 p-4 shadow-xs">
            <div className="text-3xl">⏰</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Weekly Target</div>
              <div className="font-fun text-xl font-extrabold text-ink">{totalWeeklyHours} hrs / week</div>
              <div className="text-[11px] text-good font-semibold">15% rest buffer active</div>
            </div>
          </div>
        </div>
      </section>

      {error ? <ErrorNote error={error} /> : null}

      {/* Available study time */}
      <Card
        title="⏱️ Study Time Available"
        subtitle="Minutes allocated per day for Scholr practice. The engine subtracts commitments and never over-schedules."
      >
        <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-3">
          {DAYS.map((d, i) => (
            <div
              key={d}
              className="flex flex-col rounded-2xl border border-line-soft bg-gradient-to-b from-white to-[#FDFBF7] p-3 text-center transition hover:border-brand/40"
            >
              <span className="font-fun font-bold text-xs uppercase tracking-wider text-muted">{d}</span>
              <div className="my-1.5 flex items-center justify-center">
                <input
                  type="number"
                  min={0}
                  max={720}
                  step={10}
                  value={week[i]}
                  onChange={(e) => setWeek(week.map((v, j) => (j === i ? Number(e.target.value) : v)))}
                  className="h-10 w-full rounded-xl border border-line bg-white text-center font-fun text-base font-bold text-ink focus:border-brand focus:outline-none"
                />
              </div>
              <span className="text-[11px] font-semibold text-muted">
                {minutes(week[i])}
              </span>
            </div>
          ))}
        </div>
        <div className="flex items-center justify-between pt-2 border-t border-line-soft">
          <span className="text-xs text-muted">
            Total configured: <b className="text-ink">{totalWeeklyHours} hours</b> per week
          </span>
          <div className="flex items-center gap-3">
            {saved && <span className="text-xs font-bold text-good">✓ Saved successfully!</span>}
            <Button
              onClick={() =>
                run(async () => {
                  await api(`/students/${id}/availability`, { method: "PUT", json: { minutes: week } });
                  setSaved(true);
                  setTimeout(() => setSaved(false), 3000);
                })
              }
            >
              Save Available Time
            </Button>
          </div>
        </div>
      </Card>

      {/* Commitments */}
      <Card
        title="🗓️ Fixed Commitments"
        subtitle="Coaching classes, sports, tuition, or school hours. Scholr will never schedule study during these windows."
      >
        {commitments.data?.length === 0 && (
          <Empty>No fixed commitments added yet. Add classes below to protect her time.</Empty>
        )}
        <ul className="flex flex-col gap-2.5">
          {commitments.data?.map((c) => {
            const kindColors: Record<string, { bg: string; icon: string }> = {
              iit_class: { bg: "bg-purple-100 text-purple-800", icon: "🚀" },
              extracurricular: { bg: "bg-emerald-100 text-emerald-800", icon: "⚽" },
              school: { bg: "bg-sky-100 text-sky-800", icon: "🏫" },
              other: { bg: "bg-amber-100 text-amber-800", icon: "📌" },
            };
            const meta = kindColors[c.kind] ?? { bg: "bg-gray-100 text-gray-800", icon: "•" };

            return (
              <li key={c.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line-soft bg-white/80 p-3.5 shadow-xs transition hover:border-brand/40">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#F8F5EE] text-lg">
                  {meta.icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-ink">{c.title}</span>
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${meta.bg}`}>
                      {c.kind.replace("_", " ")}
                    </span>
                  </div>
                  <div className="mt-0.5 text-xs text-muted">
                    {c.rrule.replace("FREQ=WEEKLY;BYDAY=", "Days: ").replace("FREQ=DAILY", "Daily")} · {c.start_time ?? "No start time"} · {minutes(c.duration_min)}
                  </div>
                </div>
                <button
                  className="rounded-lg px-2.5 py-1 text-xs font-semibold text-alert hover:bg-rose-50 transition"
                  onClick={() => run(async () => { await api(`/commitments/${c.id}`, { method: "DELETE" }); await commitments.reload(); })}
                >
                  Remove
                </button>
              </li>
            );
          })}
        </ul>

        {/* Add commitment form */}
        <div className="flex flex-col gap-3 rounded-2xl border border-line-soft bg-gradient-to-b from-[#FFFDF9] to-[#F7F3EB] p-4">
          <h4 className="font-fun font-bold text-sm text-ink flex items-center gap-1.5">
            <span>➕</span> Add a Recurring Commitment
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              placeholder="Commitment title (e.g. Allen Maths)"
              value={commit.title}
              onChange={(e) => setCommit({ ...commit, title: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
            />
            <select
              value={commit.kind}
              onChange={(e) => setCommit({ ...commit, kind: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
            >
              <option value="iit_class">IIT / Coaching Class</option>
              <option value="extracurricular">Activity / Sport</option>
              <option value="school">School Timetable</option>
              <option value="other">Other Activity</option>
            </select>
            <div className="flex items-center gap-2">
              <input
                type="time"
                value={commit.start_time}
                onChange={(e) => setCommit({ ...commit, start_time: e.target.value })}
                className="h-10 flex-1 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
              />
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  min={5}
                  max={720}
                  value={commit.duration_min}
                  onChange={(e) => setCommit({ ...commit, duration_min: Number(e.target.value) })}
                  className="h-10 w-16 rounded-xl border border-line bg-white px-2 text-center text-xs font-medium text-ink focus:border-brand focus:outline-none"
                />
                <span className="text-xs text-muted">min</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-muted mr-1">Repeats:</span>
              {CODES.map((code, i) => (
                <button
                  key={code}
                  type="button"
                  onClick={() => setCommit({ ...commit, days: commit.days.includes(code) ? commit.days.filter((d) => d !== code) : [...commit.days, code] })}
                  className={`h-8 w-9 rounded-xl border text-xs font-bold transition ${
                    commit.days.includes(code)
                      ? "border-brand bg-brand text-white shadow-xs"
                      : "border-line bg-white text-ink hover:border-brand/40"
                  }`}
                >
                  {DAYS[i].slice(0, 2)}
                </button>
              ))}
            </div>

            <Button
              disabled={!commit.title || commit.days.length === 0}
              onClick={() =>
                run(async () => {
                  await api(`/commitments?${query}`, { method: "POST", json: { kind: commit.kind, title: commit.title, rrule: `FREQ=WEEKLY;BYDAY=${commit.days.join(",")}`, start_time: commit.start_time, duration_min: commit.duration_min } });
                  setCommit({ ...commit, title: "", days: [] });
                  await commitments.reload();
                })
              }
            >
              Add Commitment
            </Button>
          </div>
        </div>
      </Card>

      {/* School teaching plan */}
      <TeachingPlan query={query} subjects={subjects} onError={setError} />

      {/* Upcoming school assessments */}
      <Card
        title="🎯 Upcoming School Assessments & Tests"
        subtitle="Scholr automatically schedules targeted revision sessions during the two weeks leading up to each test."
      >
        {upcoming.data?.length === 0 && (
          <Empty>No upcoming assessments scheduled. Add school tests to start 2-week preparation ramps.</Empty>
        )}
        <ul className="flex flex-col gap-2.5">
          {upcoming.data?.map((u) => (
            <li key={u.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line-soft bg-white/80 p-3.5 shadow-xs transition hover:border-brand/40">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-lg">
                📝
              </div>
              <div className="min-w-0 flex-1">
                <span className="font-bold text-ink">{u.title}</span>
                <div className="mt-0.5 text-xs text-muted flex items-center gap-2">
                  <span>📅 Due: {dateTime(u.due_at)}</span>
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                    Auto-revision active
                  </span>
                </div>
              </div>
              <button
                className="rounded-lg px-2.5 py-1 text-xs font-semibold text-alert hover:bg-rose-50 transition"
                onClick={() => run(async () => { await api(`/upcoming-assessments/${u.id}`, { method: "DELETE" }); await upcoming.reload(); })}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>

        {/* Add upcoming assessment form */}
        <div className="flex flex-col gap-3 rounded-2xl border border-line-soft bg-gradient-to-b from-[#FFFDF9] to-[#F7F3EB] p-4">
          <h4 className="font-fun font-bold text-sm text-ink flex items-center gap-1.5">
            <span>➕</span> Add an Upcoming Assessment
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <input
              placeholder="Test title (e.g. Unit 4 Algebra Mid-Term)"
              value={test.title}
              onChange={(e) => setTest({ ...test, title: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
            />
            <select
              value={test.subject_id}
              onChange={(e) => setTest({ ...test, subject_id: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
            >
              <option value="">Select Subject</option>
              {subjects.map((s) => (
                <option key={s.subject_id} value={s.subject_id}>
                  {s.subject_name}
                </option>
              ))}
            </select>
            <input
              type="datetime-local"
              value={test.due_at}
              onChange={(e) => setTest({ ...test, due_at: e.target.value })}
              className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
            />
          </div>
          <div className="flex justify-end pt-1">
            <Button
              disabled={!test.title || !test.subject_id || !test.due_at}
              onClick={() =>
                run(async () => {
                  await api(`/upcoming-assessments?${query}`, { method: "POST", json: { title: test.title, subject_id: test.subject_id, due_at: new Date(test.due_at).toISOString(), objective_ids: [] } });
                  setTest({ title: "", subject_id: "", due_at: "" });
                  await upcoming.reload();
                })
              }
            >
              Add Upcoming Test
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

