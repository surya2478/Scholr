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

// Newest series first: "MJ25" (2025, June) sorts above "ON24".
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
    <div className="flex flex-col gap-3 rounded-2xl border-2 border-amber-200/70 bg-white p-4 shadow-2xs">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="font-fun font-bold text-slate-900">{paperName(paper)}</div>
          <div className="text-xs font-medium text-slate-500">
            {duration(paper.duration_min)} · {paper.paper_marks ?? paper.bank_marks} marks
          </div>
        </div>
        {paper.in_progress ? (
          <Chip tone="warn">In progress</Chip>
        ) : paper.sat_on ? (
          <Chip tone="good">Sat {paper.sat_on}</Chip>
        ) : null}
      </div>

      {paper.assessment_id ? (
        <Link
          href={`/student/tests/${paper.assessment_id}`}
          className="self-start text-sm font-fun font-bold text-orange-600 hover:underline"
        >
          {paper.in_progress ? "Carry on with this paper →" : "See your answers and marks →"}
        </Link>
      ) : (
        <>
          {hasChoice && (
            <div className="flex flex-col gap-2 text-sm">
              <span className="text-slate-600">
                {paper.compulsory.length > 0 && <>Everyone answers {paper.compulsory.join(", ")}. </>}
                Choose {paper.choose_count} of {paper.choose_from.join(", ")}:
              </span>
              <div className="flex flex-wrap gap-2">
                {paper.choose_from.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => toggle(q)}
                    aria-pressed={chosen.includes(q)}
                    className={`rounded-full border px-3 py-1 text-xs font-bold ${
                      chosen.includes(q)
                        ? "border-orange-400 bg-orange-100 text-orange-800"
                        : "border-slate-200 bg-white text-slate-600"
                    }`}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {error ? <ErrorNote error={error} /> : null}
          <Button className="self-start" disabled={!ready || busy} onClick={start}>
            {busy ? "Starting…" : "Start timed paper"}
          </Button>
        </>
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
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-fun font-bold text-slate-900">Timed past papers</h1>
        <p className="text-sm text-slate-600 font-medium">
          Sit a real Cambridge paper under its real time limit — the best rehearsal for the exam.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {taught.map((subject) => (
          <button
            key={subject.id}
            type="button"
            onClick={() => setSubjectId(subject.id)}
            className={`rounded-full border px-4 py-1.5 text-sm font-bold ${
              subject.id === current ? "border-orange-400 bg-orange-100 text-orange-800" : "border-slate-200 bg-white text-slate-600"
            }`}
          >
            {subject.name}
          </button>
        ))}
      </div>

      {streams.error ? <ErrorNote error={streams.error} /> : null}
      {papers.error ? <ErrorNote error={papers.error} /> : null}
      {papers.data && papers.data.length === 0 && <Empty>No whole papers for this subject in the bank yet.</Empty>}

      {current && papers.data && papers.data.length > 0 && (
        <Card tone="blue">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
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
