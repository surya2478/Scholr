"use client";

import { useState } from "react";
import { ApiError, getAuthHeader, type Evaluation, type Question } from "@/lib/api";
import { api } from "@/lib/api";
import { EvaluationCard } from "./EvaluationCard";
import { MathText } from "./MathText";
import { Button, ErrorNote } from "./ui";

type PhotoAttempt = {
  id: string;
  status: string;
  transcription: { working: string | null; final_answer: string | null; legibility: string | null; uncertain: string[] } | null;
};

// Photo of handwritten working → transcription → the student confirms or edits it (AC-E3) → marking.
export function PhotoAnswer({ question, sessionId, assessmentId, markNow = true, onAnswered }: {
  question: Question;
  sessionId?: string;
  assessmentId?: string;
  markNow?: boolean;
  onAnswered?: () => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [attempt, setAttempt] = useState<PhotoAttempt | null>(null);
  const [working, setWorking] = useState("");
  const [finalAnswer, setFinal] = useState("");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function upload() {
    setBusy("Reading your working…");
    setError(null);
    const form = new FormData();
    form.set("question_item_id", question.id);
    form.set("idempotency_key", crypto.randomUUID());
    if (sessionId) form.set("session_id", sessionId);
    if (assessmentId) form.set("assessment_id", assessmentId);
    files.slice(0, 4).forEach((f) => form.append("photos", f));
    try {
      const res = await fetch("/api/attempts/photo", { method: "POST", body: form, headers: getAuthHeader() });
      const data = await res.json();
      if (!res.ok) throw new ApiError(res.status, data?.error?.code ?? "error", data?.error?.message ?? "Upload failed");
      setAttempt(data);
      setWorking(data.transcription?.working ?? "");
      setFinal(data.transcription?.final_answer ?? "");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  async function confirm() {
    if (!attempt) return;
    setBusy("Saving…");
    setError(null);
    try {
      await api(`/attempts/${attempt.id}/transcription`, { method: "PUT", json: { working, final_answer: finalAnswer || null } });
      if (markNow) {
        setBusy("Marking…");
        setEvaluation(await api<Evaluation>(`/attempts/${attempt.id}/evaluate`, { method: "POST" }));
      }
      setAttempt({ ...attempt, status: "confirmed" });
      onAnswered?.();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {!attempt && (
        <>
          <label className="flex flex-col gap-1 text-xs font-semibold text-ink-2">
            Photos of your working (up to 4)
            <input type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment" multiple onChange={(e) => setFiles(Array.from(e.target.files ?? []))} className="text-sm font-normal" />
          </label>
          <div>
            <Button disabled={files.length === 0 || Boolean(busy)} onClick={upload}>
              {busy ?? "Upload"}
            </Button>
          </div>
        </>
      )}
      {attempt && attempt.status !== "confirmed" && (
        <div className="flex flex-col gap-2 rounded-xl border border-line p-3">
          <p className="text-sm text-ink-2">
            Check what we read from your photo and fix anything wrong before it is marked.
            {attempt.transcription?.legibility === "poor" && " The photo was hard to read."}
          </p>
          {attempt.transcription?.uncertain.length ? (
            <p className="text-xs text-warn">Unsure about: {attempt.transcription.uncertain.join(", ")}</p>
          ) : null}
          <textarea value={working} onChange={(e) => setWorking(e.target.value)} rows={6} className="rounded-xl border border-line p-3 font-mono text-sm" />
          <div className="rounded-lg bg-tile p-2 text-sm">
            <MathText text={working} />
          </div>
          <input value={finalAnswer} onChange={(e) => setFinal(e.target.value)} placeholder="Final answer" className="h-10 rounded-xl border border-line px-3 text-sm" />
          <div>
            <Button disabled={Boolean(busy) || !working.trim()} onClick={confirm}>
              {busy ?? (markNow ? "Confirm and mark" : "Confirm")}
            </Button>
          </div>
        </div>
      )}
      {error ? <ErrorNote error={error} /> : null}
      {evaluation && <EvaluationCard evaluation={evaluation} />}
    </div>
  );
}
