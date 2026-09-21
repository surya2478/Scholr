"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Empty, ErrorNote } from "@/components/ui";
import { api, type ReviewItem } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

function ReviewCard({ item, onDone }: { item: ReviewItem; onDone: () => void }) {
  const e = item.evaluation;
  const [marks, setMarks] = useState(String(e.marks_awarded));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api(`/evaluations/${e.id}/override`, { method: "POST", json: { marks_awarded: Number(marks), note: note || null } });
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title={item.source_ref ?? "Question Evaluation"}
      subtitle={`AI marked ${e.marks_awarded} / ${e.marks_available} · AI Confidence: ${Math.round(item.confidence * 100)}%`}
      tone="amber"
    >
      <div className="grid gap-4 md:grid-cols-2 pt-1">
        <div className="flex flex-col gap-2 rounded-2xl bg-white border border-amber-200/80 p-4 text-xs shadow-2xs">
          <div className="text-[11px] font-fun font-bold uppercase text-orange-700">Question Prompt</div>
          {item.context && <MathText text={item.context} className="text-slate-600 mb-1" />}
          <MathText text={item.stem} className="font-semibold text-slate-900 text-sm" />
          
          <div className="mt-3 text-[11px] font-fun font-bold uppercase text-slate-500">Student&apos;s Working</div>
          <div className="bg-amber-50/50 p-2.5 rounded-xl border border-amber-200/60 font-mono text-xs">
            <MathText text={item.working ?? "(no working provided)"} />
          </div>

          <div className="mt-2 text-[11px] font-fun font-bold uppercase text-slate-500">Final Answer</div>
          <div className="bg-white p-2 rounded-xl border border-amber-200 font-mono text-xs font-bold text-slate-900">
            <MathText text={item.final_answer ?? "(no answer submitted)"} />
          </div>
        </div>

        <div className="flex flex-col gap-2 rounded-2xl bg-white border border-amber-200/80 p-4 text-xs shadow-2xs">
          <div className="text-[11px] font-fun font-bold uppercase text-emerald-700">Official Mark Scheme</div>
          <div className="bg-emerald-50/50 p-3 rounded-xl border border-emerald-200 text-xs leading-relaxed text-slate-800">
            <MathText text={item.mark_scheme || "(Mark scheme guidelines not available)"} />
          </div>

          {item.issues.length > 0 && (
            <div className="mt-2 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs space-y-1">
              <div className="font-fun font-bold text-amber-900">Why the AI requested a human review:</div>
              <ul className="list-disc pl-4 text-amber-800 space-y-0.5 font-medium">
                {item.issues.map((issue) => (
                  <li key={issue}>{issue.replaceAll("_", " ")}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3 pt-3 border-t border-slate-100">
        <label className="flex flex-col gap-1 text-xs font-fun font-bold text-slate-700">
          Confirmed Marks (Max {e.marks_available})
          <input
            type="number"
            min={0}
            max={e.marks_available}
            step={0.5}
            value={marks}
            onChange={(ev) => setMarks(ev.target.value)}
            className="h-11 w-28 rounded-2xl border-2 border-amber-200 bg-white px-3.5 text-sm font-bold text-slate-900 outline-none focus:border-orange-400"
          />
        </label>
        <label className="flex min-w-[240px] flex-1 flex-col gap-1 text-xs font-fun font-bold text-slate-700">
          Note to student (optional encouragement or explanation)
          <input
            value={note}
            maxLength={2000}
            onChange={(ev) => setNote(ev.target.value)}
            placeholder="e.g. Great method, award full method mark"
            className="h-11 rounded-2xl border-2 border-amber-200 bg-white px-3.5 text-xs font-normal text-slate-900 outline-none focus:border-orange-400"
          />
        </label>
        <Button disabled={busy} onClick={save}>
          {busy ? "Saving check…" : "Save Verified Mark ✓"}
        </Button>
      </div>
      {error ? <ErrorNote error={error} /> : null}
    </Card>
  );
}

export default function ReviewPage() {
  const { student, id, query } = useLinkedStudent();
  const list = useApi<ReviewItem[]>(id ? `/evaluations/review-queue?${query}` : null);

  if (!student) return <Empty>No student is linked to this account.</Empty>;

  return (
    <div className="space-y-6">
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="space-y-1">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-100 text-orange-800 text-xs font-fun font-bold border border-orange-200">
            <span>✏️</span> Family Quality Assurance
          </span>
          <h1 className="text-2xl md:text-3xl font-fun font-bold text-slate-900">
            Review Question Marks
          </h1>
          <p className="text-xs md:text-sm text-slate-600 font-medium max-w-2xl">
            When the AI marker detects ambiguous handwriting, photo uploads, or low-confidence rubric matching, it asks for a parent check. Overriding sets a permanent human mark.
          </p>
        </div>
      </div>

      {list.error ? <ErrorNote error={list.error} /> : null}
      {list.data?.length === 0 && (
        <Card title="Review Queue">
          <Empty>All set! No question evaluations are waiting for review right now. 🌟</Empty>
        </Card>
      )}

      <div className="space-y-4">
        {list.data?.map((item) => (
          <ReviewCard key={item.evaluation.id} item={item} onDone={() => void list.reload()} />
        ))}
      </div>
    </div>
  );
}
