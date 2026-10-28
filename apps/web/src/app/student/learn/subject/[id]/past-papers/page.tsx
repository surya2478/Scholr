"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { Chip, Empty, ErrorNote } from "@/components/ui";
import type { PastPaperItem, PastPapers } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

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
    <Chip tone="warn">{score} · pending review</Chip>
  ) : (
    <Chip tone={item.last_marks === item.marks ? "good" : "neutral"}>Score: {score}</Chip>
  );
}

export default function PastPaperHub() {
  const { id } = useParams<{ id: string }>();
  const hub = useApi<PastPapers>(`/learn/subjects/${id}/past-papers`);
  const [series, setSeries] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [expandAll, setExpandAll] = useState(false);
  const data = hub.data;

  return (
    <div className="space-y-5">
      <Link href={`/student/learn/subject/${id}`} className="text-xs font-bold text-blue-600 hover:underline">
        ← Back to {data?.subject.name ?? "Subject Syllabus"}
      </Link>

      {/* Header */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 text-white shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-2 rounded-full bg-white/10 border border-white/15 px-3 py-1 font-mono text-xs font-bold text-emerald-300">
              <span>📝 CHAPTER-BY-CHAPTER PAST-PAPER QUESTION HUB</span>
              {data?.subject.syllabus_code && <span>· {data.subject.syllabus_code}</span>}
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              {data?.subject.name ?? "Subject"}: Past-Paper Questions
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium">
              Every verified Cambridge past-paper question organized by syllabus chapter.
              {data ? ` (${data.attempted} of ${data.total} attempted)` : ""}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setExpandAll((v) => !v)}
            className="rounded-xl border border-white/20 bg-white/10 hover:bg-white/15 px-3.5 py-2 text-xs font-bold text-white cursor-pointer transition"
          >
            {expandAll ? "Collapse chapters ▲" : "Expand all chapters ▼"}
          </button>
        </div>
      </div>

      {hub.error ? <ErrorNote error={hub.error} /> : null}
      {data && data.total === 0 && <Empty>No past-paper questions for this subject yet.</Empty>}

      {data && data.series.length > 1 && (
        <div className="flex flex-wrap gap-1.5">
          {[null, ...data.series].map((s) => (
            <button
              key={s ?? "all"}
              type="button"
              onClick={() => setSeries(s)}
              className={`rounded-xl border px-3.5 py-1.5 text-xs font-bold transition cursor-pointer ${
                series === s
                  ? "border-blue-600 bg-blue-600 text-white shadow-2xs"
                  : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {s ? seriesName(s) : "All Exam Series"}
            </button>
          ))}
        </div>
      )}

      {data?.chapters.map((chapter) => {
        const items = chapter.items.filter((i) => series === null || i.series === series);
        if (items.length === 0) return null;
        const key = chapter.id ?? "untagged";
        const tried = items.filter((i) => i.last_status !== null).length;
        const isOpen = expandAll || open === key;
        return (
          <div key={key} className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs">
            <button
              type="button"
              onClick={() => setOpen((v) => (v === key ? null : key))}
              className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left cursor-pointer"
              aria-expanded={isOpen}
            >
              <span className="font-extrabold text-slate-900">{chapter.name}</span>
              <span className="font-mono text-xs font-semibold text-slate-500">
                {tried}/{items.length} attempted{" "}
                <span className={isOpen ? "inline-block rotate-90 ml-1" : "ml-1"}>›</span>
              </span>
            </button>
            {isOpen && (
              <div className="flex flex-col gap-2.5 border-t border-slate-100 p-3.5">
                {items.map((item) => (
                  <div key={item.id} className="flex flex-col gap-1">
                    <div className="flex justify-end">
                      <LastTry item={item} />
                    </div>
                    <TryQuestion
                      item={{
                        id: item.id,
                        source_ref: item.source_ref,
                        label: "",
                        marks: item.marks,
                        command_word: item.command_word,
                      }}
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
