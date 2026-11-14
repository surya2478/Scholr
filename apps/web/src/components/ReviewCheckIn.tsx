"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ReviewStatus } from "@/lib/api";
import { Button, Card, Chip, ErrorNote } from "./ui";

// The weekly check-in for marks waiting for a parent (improvement 9; GO-LIVE F12, "ten minutes on Sunday").
// Her Sociology marks do not count until a person checks them, so the check needs a time, and she is shown it.
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function daysSince(iso: string): number {
  return Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000));
}

function when(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function ReviewCheckIn({ studentId, status, onChange }: { studentId: string; status: ReviewStatus; onChange: (s: ReviewStatus) => void }) {
  const [editing, setEditing] = useState(false);
  const [weekday, setWeekday] = useState(status.weekday);
  const [time, setTime] = useState(status.time);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onChange(await api<ReviewStatus>(`/students/${studentId}/review-slot`, { method: "PUT", json: { weekday, time } }));
      setEditing(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Marks to check" action={{ href: "/parent/review", label: "Review" }}>
      <div className="space-y-2.5 text-sm text-ink-2">
        {status.waiting === 0 ? (
          <p>Nothing waiting.</p>
        ) : (
          <p>
            <b>{status.waiting}</b> answer{status.waiting === 1 ? "" : "s"} waiting for your check
            {status.oldest_waiting_since && <> · the oldest for <b>{daysSince(status.oldest_waiting_since)} days</b></>}.
            Until you check them they do not count towards her progress.
          </p>
        )}
        {status.missed && status.waiting > 0 && (
          <p className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-950">
            A weekly check-in has passed with these still waiting. She is told the same thing on her feedback.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Chip tone="brand">
            Weekly check-in: {DAYS[status.weekday]}s {status.time}
            {status.chosen ? "" : " (suggested)"}
          </Chip>
          <span className="text-muted">next {when(status.next_check)}</span>
          {!editing && (
            <button type="button" onClick={() => setEditing(true)} className="font-semibold text-brand hover:underline">
              Change
            </button>
          )}
        </div>
        {editing && (
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))} className="rounded-lg border border-line-soft bg-white px-2 py-1.5">
              {DAYS.map((d, i) => (
                <option key={d} value={i}>
                  {d}
                </option>
              ))}
            </select>
            <input type="time" value={time} onChange={(e) => setTime(e.target.value)} className="rounded-lg border border-line-soft bg-white px-2 py-1" />
            <Button disabled={busy} onClick={save}>
              Save
            </Button>
          </div>
        )}
        {error ? <ErrorNote error={error} /> : null}
        <p className="text-[11px] text-muted">
          About ten minutes a week. She sees the date on every answer that waits for you.{" "}
          <Link href="/parent/review" className="font-semibold text-brand hover:underline">
            Open the answers →
          </Link>
        </p>
      </div>
    </Card>
  );
}
