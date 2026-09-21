"use client";

import { useState } from "react";
import { ReinforcementList, StandingCards } from "@/components/Reinforcement";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type ExternalSummary, type ExternalTrainingLog } from "@/lib/api";
import { minutes, shortDate } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

// `stage`: "taught" (full engine) | "planned" (syllabus known, nothing to practise yet) | "external".
type SubjectRow = { id: string; code: string; name: string; stage: "taught" | "planned" | "external" };
type TopicNode = { id: string; code: string; name: string; children: TopicNode[]; objectives: { id: string; code: string; statement: string }[] };

const KINDS = [
  { value: "class", label: "Class" },
  { value: "test", label: "Test" },
  { value: "homework", label: "Homework" },
  { value: "practice", label: "Practice" },
];

function lessonsOf(nodes: TopicNode[]): { id: string; code: string; statement: string }[] {
  return nodes.flatMap((n) => [...n.objectives, ...lessonsOf(n.children)]);
}

const EMPTY = {
  kind: "class",
  title: "",
  occurred_on: new Date().toISOString().slice(0, 10),
  duration_min: "120",
  score: "",
  max_score: "",
  questions_attempted: "",
  questions_missed: "",
  notes: "",
};

function LogForm({ query, onSaved }: { query: string; onSaved: () => void }) {
  const subjects = useApi<SubjectRow[]>("/subjects");
  const [subjectId, setSubjectId] = useState("");
  const tree = useApi<{ topics: TopicNode[] }>(subjectId ? `/subjects/${subjectId}/tree` : null);
  const [form, setForm] = useState(EMPTY);
  const [covered, setCovered] = useState<string[]>([]);
  const [weak, setWeak] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);

  const external = (subjects.data ?? []).filter((s) => s.stage === "external");
  const lessons = tree.data ? lessonsOf(tree.data.topics) : [];
  const number = (value: string) => (value.trim() === "" ? null : Number(value));

  async function save() {
    setError(null);
    setSaving(true);
    try {
      await api(`/external-training?${query}`, {
        method: "POST",
        json: {
          subject_id: subjectId,
          kind: form.kind,
          title: form.title,
          occurred_on: form.occurred_on,
          duration_min: number(form.duration_min),
          objective_ids: covered,
          weak_objective_ids: weak.filter((id) => covered.includes(id)),
          score: number(form.score),
          max_score: number(form.max_score),
          questions_attempted: number(form.questions_attempted),
          questions_missed: number(form.questions_missed),
          notes: form.notes.trim() || null,
        },
      });
      setForm({ ...EMPTY, kind: form.kind });
      setCovered([]);
      setWeak([]);
      onSaved();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  function toggle(list: string[], set: (v: string[]) => void, id: string) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  }

  return (
    <Card
      title="📝 Record a Class, Test or Homework"
      subtitle="Scholr connects external coaching syllabi with Cambridge foundations to reinforce prerequisite concepts."
    >
      {error ? <ErrorNote error={error} /> : null}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2.5">
        <select
          value={subjectId}
          onChange={(e) => {
            setSubjectId(e.target.value);
            setCovered([]);
            setWeak([]);
          }}
          className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
        >
          <option value="">Select Course</option>
          {external.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
        <select
          value={form.kind}
          onChange={(e) => setForm({ ...form, kind: e.target.value })}
          className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
        >
          {KINDS.map((k) => (
            <option key={k.value} value={k.value}>
              {k.label}
            </option>
          ))}
        </select>
        <input
          placeholder="Session title (e.g. Saturday Allen Maths)"
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          className="h-10 md:col-span-2 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
        />
        <div className="grid grid-cols-2 gap-1.5">
          <input
            type="date"
            value={form.occurred_on}
            onChange={(e) => setForm({ ...form, occurred_on: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-2 text-[11px] font-medium text-ink focus:border-brand focus:outline-none"
          />
          <input
            type="number"
            min={0}
            max={720}
            placeholder="Min"
            value={form.duration_min}
            onChange={(e) => setForm({ ...form, duration_min: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-2 text-center text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-5 gap-2.5 pt-1">
        <label className="flex flex-col gap-1 text-[11px] font-bold text-muted">
          Score Obtained
          <input
            type="number"
            min={0}
            placeholder="Marks"
            value={form.score}
            onChange={(e) => setForm({ ...form, score: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-bold text-muted">
          Max Score
          <input
            type="number"
            min={1}
            placeholder="Out of"
            value={form.max_score}
            onChange={(e) => setForm({ ...form, max_score: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-bold text-muted">
          Questions Attempted
          <input
            type="number"
            min={0}
            placeholder="Attempted"
            value={form.questions_attempted}
            onChange={(e) => setForm({ ...form, questions_attempted: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-bold text-muted">
          Questions Missed
          <input
            type="number"
            min={0}
            placeholder="Missed"
            value={form.questions_missed}
            onChange={(e) => setForm({ ...form, questions_missed: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-bold text-muted sm:col-span-4 md:col-span-1">
          Private Notes
          <input
            placeholder="Optional comments..."
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            className="h-10 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
        </label>
      </div>

      {lessons.length > 0 && (
        <div className="flex flex-col gap-2 rounded-2xl border border-line-soft bg-[#FAF7F0] p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold text-ink">
              Select Lessons & Concepts Covered:
            </span>
            <div className="flex items-center gap-2 text-[11px]">
              <span className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 font-semibold text-brand-strong">
                <span>1 tap</span> = Covered
              </span>
              <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2 py-0.5 font-semibold text-rose-800">
                <span>2 taps</span> = Struggled
              </span>
            </div>
          </div>

          <div className="flex max-h-56 flex-wrap gap-1.5 overflow-y-auto rounded-xl border border-line-soft bg-white/80 p-3">
            {lessons.map((lesson) => {
              const isCovered = covered.includes(lesson.id);
              const isWeak = weak.includes(lesson.id);
              return (
                <button
                  key={lesson.id}
                  type="button"
                  onClick={() =>
                    isCovered && !isWeak
                      ? toggle(weak, setWeak, lesson.id)
                      : isWeak
                        ? (toggle(weak, setWeak, lesson.id), toggle(covered, setCovered, lesson.id))
                        : toggle(covered, setCovered, lesson.id)
                  }
                  className={`rounded-full border px-3 py-1.5 text-xs transition ${
                    isWeak
                      ? "border-rose-300 bg-rose-100 font-bold text-rose-800 shadow-xs"
                      : isCovered
                        ? "border-brand bg-brand font-bold text-white shadow-xs"
                        : "border-line bg-white text-ink hover:border-brand/40"
                  }`}
                >
                  {isWeak ? "⚠️ " : isCovered ? "✓ " : ""}{lesson.statement}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-line-soft">
        <span className="text-xs text-muted">
          <b className="text-ink">{covered.length}</b> lesson{covered.length === 1 ? "" : "s"} covered ·{" "}
          <b className="text-rose-600">{weak.filter((id) => covered.includes(id)).length}</b> struggled with
        </span>
        <Button disabled={!subjectId || !form.title || saving} onClick={save}>
          {saving ? "Saving Training Log…" : "Save Training Session"}
        </Button>
      </div>
    </Card>
  );
}

function RecentLogs({ logs }: { logs: ExternalTrainingLog[] }) {
  return (
    <Card title="🕒 Recently Recorded Sessions">
      {logs.length === 0 && <Empty>No coaching sessions recorded yet.</Empty>}
      <ul className="flex flex-col gap-2.5">
        {logs.map((log) => (
          <li key={log.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line-soft bg-white/80 p-3.5 shadow-xs transition hover:border-brand/40">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-50 text-lg">
              🚀
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <b className="font-bold text-ink">{log.title}</b>
                <span className="rounded-full bg-purple-100 px-2 py-0.5 text-[11px] font-bold text-purple-800 capitalize">
                  {log.kind}
                </span>
                <span className="text-xs text-muted">
                  · {log.subject_name} · {shortDate(log.occurred_on)}
                </span>
              </div>
              <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-muted">
                {log.duration_min ? <span>⏱️ {minutes(log.duration_min)}</span> : null}
                {log.score !== null && log.max_score !== null ? (
                  <span className="rounded-md bg-amber-50 px-1.5 py-0.5 font-bold text-amber-800">
                    Score: {log.score}/{log.max_score}
                  </span>
                ) : null}
                {log.weak_lessons.length > 0 && (
                  <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700">
                    Struggled: {log.weak_lessons.map((l) => l.title).join(", ")}
                  </span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function ParentIit() {
  const { id, query } = useLinkedStudent();
  const summary = useApi<ExternalSummary>(id ? `/external-training/summary?${query}` : null);

  return (
    <div className="flex flex-col gap-6">
      {/* Friendly banner */}
      <section className="relative overflow-hidden rounded-3xl border border-purple-100 bg-gradient-to-r from-[#F5F3FF] via-[#FAF5FF] to-[#EFF6FF] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-purple-800 shadow-xs">
              <span>🚀</span> Dual Curriculum Bridge
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              IIT Foundation & Coaching Support
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Log external coaching classes, homework, and test scores. Scholr automatically links topics to underlying Cambridge IGCSE objectives so both courses strengthen each other without double workload.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-purple-200/60 bg-white/90 p-4 shadow-xs">
            <div className="text-3xl">🌉</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Zero Overlap</div>
              <div className="font-fun text-sm font-bold text-ink">Synergistic Learning</div>
              <div className="text-[11px] text-muted">IGCSE + IIT Foundation</div>
            </div>
          </div>
        </div>
      </section>

      {summary.error ? <ErrorNote error={summary.error} /> : null}
      {id && <LogForm query={query} onSaved={summary.reload} />}

      <Card title="📊 Coaching Standing & Attendance" subtitle="Attendance streaks, scores, and difficult topics that need reinforcement.">
        <StandingCards subjects={summary.data?.subjects ?? []} />
      </Card>

      <ReinforcementList
        targets={summary.data?.reinforcement ?? []}
        subtitle="IGCSE topics that will make upcoming external coaching classes easier. High priority topics are scheduled into her daily missions."
        emptyText="Nothing to reinforce right now — record a coaching class she found challenging and targeted Cambridge topics will appear here."
      />

      <RecentLogs logs={summary.data?.recent ?? []} />
    </div>
  );
}
