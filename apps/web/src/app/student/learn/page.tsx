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
      <div>
        <h1 className="text-2xl font-fun font-bold text-slate-900">Subjects &amp; topics</h1>
        <p className="text-sm text-slate-600 font-medium">
          Open a subject to see its chapters. Every topic has a lesson, questions to try, and the Tutor for doubts.
        </p>
      </div>
      {streams.error ? <ErrorNote error={streams.error} /> : null}
      {streams.loading && <p className="text-sm text-slate-500">Loading your subjects…</p>}
      {(streams.data ?? []).map((stream) => (
        <StreamSection key={stream.key} stream={stream} />
      ))}
    </div>
  );
}
