"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, Card, ErrorNote } from "@/components/ui";
import { ApiError, getAuthHeader, type HomeworkPhoto } from "@/lib/api";

// Photograph the homework you have been set, land on the topic it is on (docs/GO-LIVE-ENGAGEMENT.md F3).
// This page never answers the homework: it offers topics, she picks one, and the topic page takes over with the
// lesson, the questions on it and the Tutor — which asks for an attempt before it helps, as everywhere else.
export default function HomeworkPhotoPage() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<HomeworkPhoto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function send() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.set("photo", file);
    try {
      const res = await fetch("/api/learn/homework-photo", {
        method: "POST",
        body: form,
        headers: getAuthHeader(),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = (data as { error?: { code?: string; message?: string } }).error ?? {};
        throw new ApiError(res.status, err.code ?? "error", err.message ?? "That photo could not be read.");
      }
      setResult(data as HomeworkPhoto);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div>
        <h1 className="text-2xl font-fun font-bold text-ink">What have you been set?</h1>
        <p className="mt-1 text-sm font-medium text-muted">
          Photograph your worksheet or exercise book and Scholr will find the topic it is on, so you can read it up
          and practise before you start. It reads the questions only — it will not do the work for you.
        </p>
      </div>

      <Card title="Take a photo">
        <label className="flex flex-col gap-2">
          <span className="text-xs font-bold text-slate-700">A page of your homework</span>
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            capture="environment"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setResult(null);
            }}
            className="text-xs"
          />
        </label>
        <p className="text-[11px] text-slate-500">
          The photo is read once and then thrown away — it is not saved, and nor is what it says.
        </p>
        {error ? <ErrorNote error={error} /> : null}
        <div className="flex items-center gap-3">
          <Button disabled={!file || busy} onClick={send}>
            {busy ? "Reading the page…" : "Find the topic"}
          </Button>
          {file ? <span className="text-[11px] text-slate-500">{file.name}</span> : null}
        </div>
      </Card>

      {result ? (
        <Card
          title={result.matches.length > 0 ? "Is it one of these?" : "I could not place it"}
          subtitle={result.matches.length > 0 ? "Pick the topic that matches what you have been set." : undefined}
        >
          {result.text_preview ? (
            <p className="rounded-xl border border-slate-200 bg-slate-50/70 p-3 text-xs text-slate-700">
              <span className="font-bold">What I read:</span> {result.text_preview}
            </p>
          ) : null}

          {result.notice ? <p className="text-xs font-medium text-slate-700">{result.notice}</p> : null}

          <ul className="flex flex-col gap-2">
            {result.matches.map((m) => (
              <li key={m.objective_id}>
                <Link
                  href={`/student/learn/topic/${m.objective_id}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-xl border border-slate-200 bg-white p-3 transition hover:border-blue-400"
                >
                  <span className="text-xs font-bold text-slate-900">
                    {m.subject_name} · {m.code} {m.statement}
                  </span>
                  <span className="text-[11px] font-medium text-blue-600">Open this topic →</span>
                </Link>
              </li>
            ))}
          </ul>

          <p className="text-xs text-slate-600">
            None of these?{" "}
            <Link href="/student/learn" className="font-bold text-blue-600 hover:underline">
              Pick the topic yourself
            </Link>
            .
          </p>
        </Card>
      ) : null}
    </div>
  );
}
