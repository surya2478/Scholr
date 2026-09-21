"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { Chip, Empty, ErrorNote } from "@/components/ui";
import type { PastPaperItem, PastPapers } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

// Past-paper hub (docs/STUDENT-APP.md step 4): every real Cambridge question in the subject, chapter by chapter,
// newest series first, with her last try. Examiner comments appear once an answer is marked (AC-R6).
const SERIES_NAMES: Record<string, string> = { FM: "Feb/March", MJ: "May/June", ON: "Oct/Nov" };

function seriesName(series: string | null): string {
  if (!series || series.length !== 4) return series ?? "";
  return `${SERIES_NAMES[series.slice(0, 2)] ?? series.slice(0, 2)} 20${series.slice(2)}`;
}

function LastTry({ item }: { item: PastPaperItem }) {
  if (item.last_status === null) return null;
  if (item.last_status === "answered") return <Chip tone="brand">Answered</Chip>;
  const score = `${item.last_marks ?? 0}/${item.marks}`;
  return item.last_status === "provisional" ? (
    <Chip tone="warn">{score} · parent to check</Chip>
  ) : (
    <Chip tone={item.last_marks === item.marks ? "good" : "neutral"}>Last try {score}</Chip>
  );
}

export default function PastPaperHub() {
  const { id } = useParams<{ id: string }>();
  const hub = useApi<PastPapers>(`/learn/subjects/${id}/past-papers`);
  const [series, setSeries] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const data = hub.data;

  return (
    <div className="space-y-5">
      <Link href={`/student/learn/subject/${id}`} className="text-xs font-bold text-orange-600 hover:underline">
        ← {data?.subject.name ?? "Subject"}
      </Link>
      <div>
        <h1 className="text-2xl font-fun font-bold text-slate-900">Past-paper questions</h1>
        <p className="text-sm text-slate-600 font-medium">
          Real Cambridge questions, by chapter.
          {data ? ` ${data.attempted} of ${data.total} tried.` : ""} After marking you&apos;ll see what the examiners said.
        </p>
      </div>
      {hub.error ? <ErrorNote error={hub.error} /> : null}
      {data && data.total === 0 && <Empty>No past-paper questions for this subject yet.</Empty>}

      {data && data.series.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {[null, ...data.series].map((s) => (
            <button
              key={s ?? "all"}
              type="button"
              onClick={() => setSeries(s)}
              className={`rounded-full border px-3 py-1 text-xs font-bold ${
                series === s ? "border-orange-400 bg-orange-100 text-orange-800" : "border-slate-200 bg-white text-slate-600"
              }`}
            >
              {s ? seriesName(s) : "All series"}
            </button>
          ))}
        </div>
      )}

      {data?.chapters.map((chapter) => {
        const items = chapter.items.filter((i) => series === null || i.series === series);
        if (items.length === 0) return null;
        const key = chapter.id ?? "untagged";
        const tried = items.filter((i) => i.last_status !== null).length;
        return (
          <div key={key} className="rounded-2xl border-2 border-amber-200/70 bg-white shadow-2xs">
            <button
              type="button"
              onClick={() => setOpen((v) => (v === key ? null : key))}
              className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
              aria-expanded={open === key}
            >
              <span className="font-fun font-bold text-slate-900">{chapter.name}</span>
              <span className="text-xs font-semibold text-slate-500">
                {tried}/{items.length} tried <span className={open === key ? "inline-block rotate-90" : ""}>›</span>
              </span>
            </button>
            {open === key && (
              <div className="flex flex-col gap-2 border-t border-amber-100 p-3">
                {items.map((item) => (
                  <div key={item.id} className="flex flex-col gap-1">
                    <div className="flex justify-end">
                      <LastTry item={item} />
                    </div>
                    <TryQuestion
                      item={{ id: item.id, source_ref: item.source_ref, label: "", marks: item.marks, command_word: item.command_word }}
                      label={`${seriesName(item.series)} · Paper ${item.paper} · Q${item.question}`}
                      askHref={(q) => tutorHref({ subjectId: id, ask: q })}
                      onAnswered={() => void hub.reload()}
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
