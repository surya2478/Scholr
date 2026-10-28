"use client";

import { StreamSection } from "@/components/learn/Streams";
import { ErrorNote } from "@/components/ui";
import type { Stream } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// Learn: every stream and subject, from the subject configs (docs/STUDENT-APP.md, AC-U1).
export default function Learn() {
  const streams = useApi<Stream[]>("/learn/streams");
  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 md:p-6 shadow-2xs">
        <div className="font-mono text-xs font-bold uppercase tracking-wider text-blue-600">
          CAMBRIDGE CIE &amp; IIT FOUNDATION CURRICULUM
        </div>
        <h1 className="mt-1 text-2xl font-extrabold text-slate-900">Syllabus &amp; Revision Notes</h1>
        <p className="mt-1 text-xs md:text-sm text-slate-600 font-medium">
          Select a subject to open its revision notes, cheat sheets, recall flashcards and topic questions (<code className="font-mono text-xs text-blue-600">Easy → Medium → Hard</code>).
        </p>
      </div>
      {streams.error ? <ErrorNote error={streams.error} /> : null}
      {streams.loading && <p className="text-sm text-slate-500">Loading syllabus streams…</p>}
      {(streams.data ?? []).map((stream) => (
        <StreamSection key={stream.key} stream={stream} />
      ))}
    </div>
  );
}
