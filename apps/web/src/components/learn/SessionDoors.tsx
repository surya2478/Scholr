"use client";

import Link from "next/link";
import type { SessionDoor } from "@/lib/api";

// Three ways into today's work, so "I haven't got time to start" stops being a reason not to
// (docs/GO-LIVE-ENGAGEMENT.md F2). Every minute figure is the API's, computed from the door's own content —
// nothing here rounds a door to the size it was aiming at, and a closed door stays visible with its reason.
const DOORS: Record<SessionDoor["key"], { title: string; href: (door: SessionDoor) => string }> = {
  quick: { title: "A couple of minutes", href: () => "/student/practice/memory-boost" },
  today: { title: "Today's set", href: () => "/student/practice/daily" },
  deep: {
    title: "One topic, properly",
    href: (door) => (door.objective_id ? `/student/learn/topic/${door.objective_id}` : "/student/learn"),
  },
};

function Door({ door }: { door: SessionDoor }) {
  const meta = DOORS[door.key];
  const body = (
    <>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-fun font-bold text-ink">{meta.title}</span>
        {door.open ? (
          <span className="font-mono text-xs font-bold text-blue-700">about {door.minutes} min</span>
        ) : null}
      </div>
      <p className="mt-1 text-xs font-medium text-muted">{door.open ? door.text : door.closed_reason}</p>
      {door.open && door.key === "deep" && door.objective_code ? (
        <p className="mt-1.5 line-clamp-2 text-[11px] text-slate-500">
          {door.objective_code} {door.objective_statement}
          {door.parts.length > 0 ? ` · starts with ${door.parts[0]}` : ""}
          {door.parts.length > 1 ? `, then ${door.parts.slice(1).join(" and ")}` : ""}
        </p>
      ) : null}
      {door.open && door.questions > 0 ? (
        <p className="mt-1.5 text-[11px] text-slate-500">
          {door.questions} question{door.questions === 1 ? "" : "s"}
        </p>
      ) : null}
    </>
  );

  if (!door.open) {
    return (
      <div className="flex h-full flex-col rounded-2xl border border-line-soft bg-tile p-4 text-ink-2">{body}</div>
    );
  }
  return (
    <Link
      href={meta.href(door)}
      className="flex h-full flex-col rounded-2xl border border-line bg-white p-4 shadow-2xs transition hover:border-brand hover:shadow-sm"
    >
      {body}
    </Link>
  );
}

export function SessionDoors({ doors }: { doors: SessionDoor[] }) {
  if (doors.length === 0) return null;
  return (
    <section className="space-y-2.5">
      <div>
        <h2 className="text-lg font-fun font-bold text-ink">How long have you got?</h2>
        <p className="text-xs font-medium text-muted">
          Each one says how long it really takes, worked out from the questions and the lesson themselves.
        </p>
      </div>
      <div className="grid grid-cols-1 items-stretch gap-3 md:grid-cols-3">
        {doors.map((door) => (
          <Door key={door.key} door={door} />
        ))}
      </div>
    </section>
  );
}
