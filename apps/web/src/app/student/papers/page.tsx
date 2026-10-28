"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type PaperToSit, type Sitting, type Stream } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// Timed past papers (Phase 2 AC-R3): the whole paper, its real time limit and the syllabus's own question choice.
// No hints or Tutor until it is submitted; answers are marked after submission.
const SERIES_NAMES: Record<string, string> = { FM: "Feb/March", MJ: "May/June", ON: "Oct/Nov" };

function paperName(paper: PaperToSit): string {
  const [, component, series] = paper.paper_ref.split("/");
  const when = series ? `${SERIES_NAMES[series.slice(0, 2)] ?? series.slice(0, 2)} 20${series.slice(2)}` : "";
  return `Paper ${component} · ${when}`;
}

const SERIES_MONTH: Record<string, number> = { FM: 3, MJ: 6, ON: 11 };

function seriesOrder(paper: PaperToSit): number {
  const series = paper.paper_ref.split("/")[2] ?? "";
  return Number(series.slice(2)) * 100 + (SERIES_MONTH[series.slice(0, 2)] ?? 0);
}

function duration(minutes: number | null): string {
  if (!minutes) return "untimed";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h} h${m ? ` ${m} min` : ""}` : `${m} min`;
}

function PaperCard({ subjectId, paper }: { subjectId: string; paper: PaperToSit }) {
  const router = useRouter();
  const [chosen, setChosen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const hasChoice = paper.choose_count > 0;
  const ready = !hasChoice || chosen.length === paper.choose_count;

  function toggle(q: string) {
    setChosen((prev) =>
      prev.includes(q) ? prev.filter((x) => x !== q) : prev.length < paper.choose_count ? [...prev, q] : prev,
    );
  }

  async function start() {
    const warning =
      `Start ${paperName(paper)} now? The clock runs for ${duration(paper.duration_min)}. ` +
      "There are no hints and no Tutor until you submit, and answers are marked after you submit.";
    if (!window.confirm(warning)) return;
    setBusy(true);
    setError(null);
    try {
      const sitting = await api<Sitting>(`/subjects/${subjectId}/sittings`, {
        method: "POST",
        json: { paper_ref: paper.paper_ref, questions: chosen },
      });
      router.push(`/student/tests/${sitting.assessment_id}`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col justify-between gap-3.5 rounded-2xl border border-slate-200/90 bg-white p-4.5 shadow-2xs transition hover:border-blue-400">
      <div className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div className="font-extrabold text-slate-900 text-base">{paperName(paper)}</div>
            <div className="font-mono text-xs font-semibold text-slate-500 mt-0.5">
              ⏱️ {duration(paper.duration_min)} · {paper.paper_marks ?? paper.bank_marks} marks · Ref: {paper.paper_ref}
            </div>
          </div>
          {paper.in_progress ? (
            <Chip tone="warn">In progress</Chip>
          ) : paper.sat_on ? (
            <Chip tone="good">Sat {paper.sat_on}</Chip>
          ) : (
            <Chip tone="brand">Official CIE Paper</Chip>
          )}
        </div>

        {hasChoice && !paper.assessment_id && (
          <div className="flex flex-col gap-2 rounded-xl bg-slate-50 p-3 border border-slate-200/80 text-xs">
            <span className="text-slate-600 font-medium">
              {paper.compulsory.length > 0 && <>Compulsory: {paper.compulsory.join(", ")}. </>}
              Select {paper.choose_count} optional section{paper.choose_count === 1 ? "" : "s"} from {paper.choose_from.join(", ")}:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {paper.choose_from.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => toggle(q)}
                  aria-pressed={chosen.includes(q)}
                  className={`rounded-lg border px-3 py-1 font-mono text-xs font-bold transition cursor-pointer ${
                    chosen.includes(q)
                      ? "border-blue-600 bg-blue-600 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {paper.assessment_id ? (
        <Link
          href={`/student/tests/${paper.assessment_id}`}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:underline pt-1"
        >
          <span>{paper.in_progress ? "▶ Resume timed paper sitting" : "📊 Review marked script & examiner report"}</span>
          <span>→</span>
        </Link>
      ) : (
        <div className="pt-1">
          {error ? <ErrorNote error={error} /> : null}
          <Button disabled={!ready || busy} onClick={start}>
            {busy ? "Initialising exam clock…" : "Start Timed Paper Sitting →"}
          </Button>
        </div>
      )}
    </div>
  );
}

export default function TimedPapers() {
  const streams = useApi<Stream[]>("/learn/streams");
  const taught = (streams.data ?? []).flatMap((s) => s.subjects).filter((s) => s.stage === "taught");
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const current = subjectId ?? taught[0]?.id ?? null;
  const papers = useApi<PaperToSit[]>(current ? `/subjects/${current}/past-papers` : null);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-3xl bg-gradient-to-r from-[#0B1528] via-[#13294B] to-[#1E3A8A] p-6 md:p-8 text-white shadow-xl">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-2">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 text-emerald-300 font-mono text-xs font-bold border border-white/15">
              <span>⏱️</span> OFFICIAL CAMBRIDGE CIE PAST-PAPER ARCHIVE
            </span>
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight">
              Timed Past-Paper Sittings
            </h1>
            <p className="text-xs md:text-sm text-slate-300 font-medium max-w-2xl leading-relaxed">
              Sit complete Cambridge IGCSE past papers under strict exam clock conditions with real section choices and post-submission rubric marking.
            </p>
          </div>
          <div className="h-14 w-14 rounded-2xl bg-white/10 border border-white/15 flex items-center justify-center font-mono text-lg font-extrabold text-emerald-300 flex-none">
            CIE
          </div>
        </div>
      </div>

      {/* Subject Filter Tabs */}
      <div className="flex flex-wrap gap-2">
        {taught.map((subject) => {
          const active = subject.id === current;
          return (
            <button
              key={subject.id}
              type="button"
              onClick={() => setSubjectId(subject.id)}
              className={`rounded-xl border px-4 py-2 text-xs font-bold transition cursor-pointer ${
                active
                  ? "border-blue-600 bg-blue-600 text-white shadow-2xs"
                  : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
              }`}
            >
              <span>{subject.name}</span>
              {subject.syllabus_code && (
                <span className={`ml-2 font-mono text-[11px] ${active ? "text-blue-100" : "text-slate-400"}`}>
                  ({subject.syllabus_code})
                </span>
              )}
            </button>
          );
        })}
      </div>

      {streams.error ? <ErrorNote error={streams.error} /> : null}
      {papers.error ? <ErrorNote error={papers.error} /> : null}
      {papers.data && papers.data.length === 0 && (
        <Empty>No complete timed papers for this subject have been indexed yet.</Empty>
      )}

      {current && papers.data && papers.data.length > 0 && (
        <Card
          title="Available Past Papers (Newest Series First)"
          subtitle="Select a paper to begin a full timed sitting or review your marked script"
          tone="blue"
        >
          <div className="grid grid-cols-1 gap-3.5 md:grid-cols-2">
            {[...papers.data]
              .sort((a, b) => seriesOrder(b) - seriesOrder(a) || a.paper_ref.localeCompare(b.paper_ref))
              .map((paper) => (
                <PaperCard key={paper.paper_ref} subjectId={current} paper={paper} />
              ))}
          </div>
        </Card>
      )}
    </div>
  );
}
