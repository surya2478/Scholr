"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type ClassCheckIn as CheckIn } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Card, ErrorNote } from "./ui";

// "What did class cover today?" (docs/GO-LIVE-ENGAGEMENT.md F4, improvement 7). Two taps: a subject's chapter.
// The tap becomes her own teaching-plan entry: "lock it in tonight" opens the chapter at once, and the next days'
// plans offer it as the current school topic for a week.
// "No class today" is remembered in this browser only, for today only: a convenience, never a record.
const SKIP_KEY = "scholr.class_check_in_skipped";

function skippedToday(day: string): string[] {
  try {
    const raw = window.localStorage.getItem(SKIP_KEY);
    const parsed = raw ? (JSON.parse(raw) as { day: string; subjects: string[] }) : null;
    return parsed && parsed.day === day ? parsed.subjects : [];
  } catch {
    return [];
  }
}

function rememberSkip(day: string, subjects: string[]) {
  try {
    window.localStorage.setItem(SKIP_KEY, JSON.stringify({ day, subjects }));
  } catch {
    // Private window or blocked storage: the card simply asks again.
  }
}

export function ClassCheckIn() {
  const checkIn = useApi<CheckIn>("/class-check-in");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [skipped, setSkipped] = useState<string[]>([]);
  const data = checkIn.data;

  useEffect(() => {
    if (data) setSkipped(skippedToday(data.day));
  }, [data]);

  if (!data || data.subjects.length === 0) return null;
  const anyLogged = data.subjects.some((x) => x.logged.length > 0);
  if (!data.school_day && !anyLogged) return null;
  const open = data.subjects.filter((x) => x.logged.length === 0 && !skipped.includes(x.subject_id));
  const done = data.subjects.filter((x) => x.logged.length > 0);
  if (open.length === 0 && done.length === 0) return null;

  async function tap(subjectId: string, topicId: string) {
    setBusy(subjectId);
    setError(null);
    try {
      checkIn.setData(await api<CheckIn>("/class-check-in", { method: "POST", json: { subject_id: subjectId, topic_id: topicId } }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  async function undo(entryId: string) {
    setError(null);
    try {
      await api(`/teaching-plan/${entryId}`, { method: "DELETE" });
      await checkIn.reload();
    } catch (err) {
      setError(err);
    }
  }

  function skip(subjectId: string) {
    const next = [...skipped, subjectId];
    setSkipped(next);
    rememberSkip(data!.day, next);
  }

  return (
    <Card
      title="What did class cover today?"
      subtitle="Two taps. Lock it in tonight while it's fresh; your plan follows your class for the next week."
    >
      {error ? <ErrorNote error={error} /> : null}
      <div className="flex flex-col gap-4">
        {done.map((subject) =>
          subject.logged.map((l) => (
            <div key={l.entry_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5">
              <span className="text-xs text-emerald-950">
                <b>{subject.subject_name}</b> covered <b>{l.name}</b>
              </span>
              <span className="flex items-center gap-3 text-xs font-bold">
                {l.next_objective_id && (
                  <Link href={`/student/learn/topic/${l.next_objective_id}`} className="text-brand hover:underline">
                    Lock it in tonight: {l.next_objective_code} →
                  </Link>
                )}
                <button type="button" onClick={() => undo(l.entry_id)} className="text-muted hover:text-ink">
                  Undo
                </button>
              </span>
            </div>
          )),
        )}

        {open.map((subject) => (
          <div key={subject.subject_id} className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wide text-muted">{subject.subject_name}</span>
              <button type="button" onClick={() => skip(subject.subject_id)} className="text-[11px] font-semibold text-muted hover:text-ink">
                No class today
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {subject.suggestions.map((c) => (
                <button
                  key={c.topic_id}
                  type="button"
                  disabled={busy === subject.subject_id}
                  onClick={() => tap(subject.subject_id, c.topic_id)}
                  className="rounded-xl border border-line-soft bg-tile px-3 py-2 text-left text-xs font-semibold text-ink-2 transition hover:border-brand disabled:opacity-50"
                >
                  {c.name}
                </button>
              ))}
              {subject.others.length > 0 && (
                <select
                  aria-label={`Another ${subject.subject_name} chapter`}
                  disabled={busy === subject.subject_id}
                  value=""
                  onChange={(e) => e.target.value && tap(subject.subject_id, e.target.value)}
                  className="rounded-xl border border-line-soft bg-white px-3 py-2 text-xs font-semibold text-ink-2"
                >
                  <option value="">Something else…</option>
                  {subject.others.map((c) => (
                    <option key={c.topic_id} value={c.topic_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}
