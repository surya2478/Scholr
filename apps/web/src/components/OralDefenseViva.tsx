"use client";

import { useEffect, useRef, useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type VivaQuestion, type VivaStep, type VivaTopic } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { MAX_SECONDS, type Recording, startRecording, toBase64 } from "@/lib/voiceRecorder";

// Oral defence (docs/STUDENT-APP.md §19): a real past-paper question, solved one step at a time. Before each step is
// shown she says or types what she would do next and why; the API judges that against the approved solution's
// step only, and checks the verdict in code. It is feedback on her reasoning, never a mark — no score, no points.
// Voice goes through Scholr's own transcription (the Tutor's), not the browser's speech service.

const VERDICT: Record<VivaStep["verdict"], { label: string; tone: "good" | "warn" | "neutral" | "alert" }> = {
  right: { label: "That's the step", tone: "good" },
  partly: { label: "Nearly", tone: "warn" },
  not_yet: { label: "Not yet", tone: "neutral" },
  safety: { label: "Let's pause", tone: "alert" },
};

type Done = { text: string; mark: string; verdict: VivaStep["verdict"] };

export function OralDefenseViva({ subjectId }: { subjectId: string }) {
  const topics = useApi<VivaTopic[]>(subjectId ? `/learn/viva?subject_id=${subjectId}` : null);
  const [question, setQuestion] = useState<VivaQuestion | null>(null);
  const [done, setDone] = useState<Done[]>([]);
  const [explanation, setExplanation] = useState("");
  const [judged, setJudged] = useState<VivaStep | null>(null);
  const [busy, setBusy] = useState(false);
  const [voice, setVoice] = useState<"idle" | "recording" | "transcribing">("idle");
  const [error, setError] = useState<unknown>(null);
  const recording = useRef<Recording | null>(null);

  useEffect(() => () => recording.current?.cancel(), []);

  const index = done.length + 1; // the step she is explaining (1-based)
  const finished = question !== null && done.length === question.steps;

  async function open(topic: VivaTopic) {
    setError(null);
    setDone([]);
    setJudged(null);
    setExplanation("");
    try {
      setQuestion(await api<VivaQuestion>(`/learn/viva/${topic.objective_id}`));
    } catch (err) {
      setError(err);
    }
  }

  async function defend() {
    if (!question || !explanation.trim()) return;
    setBusy(true);
    setError(null);
    try {
      setJudged(
        await api<VivaStep>(`/learn/viva/${question.objective_id}/steps/${index}`, {
          method: "POST",
          json: { explanation: explanation.trim() },
        })
      );
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function showStep() {
    if (!judged) return;
    setDone((d) => [...d, { text: judged.step_text, mark: judged.step_mark, verdict: judged.verdict }]);
    setJudged(null);
    setExplanation("");
  }

  async function toggleVoice() {
    if (voice === "transcribing") return;
    if (voice === "idle") {
      try {
        recording.current = await startRecording();
        setVoice("recording");
        setTimeout(() => void finishVoice(), MAX_SECONDS * 1000);
      } catch {
        setError(new Error("The microphone isn't available. Check the browser's permission, or type instead."));
      }
      return;
    }
    await finishVoice();
  }

  async function finishVoice() {
    const current = recording.current;
    recording.current = null;
    if (!current) return;
    setVoice("transcribing");
    try {
      const wav = await current.stop();
      const heard = await api<{ text: string }>("/tutor/speech", {
        method: "POST",
        json: { audio: await toBase64(wav), format: "wav" },
      });
      setExplanation((prev) => (prev ? `${prev} ${heard.text}` : heard.text));
    } catch (err) {
      setError(err);
    } finally {
      setVoice("idle");
    }
  }

  return (
    <Card
      title="🎓 Oral defence"
      subtitle="A real exam question, one step at a time: say what you'd do next and why, before you see it"
      tone="purple"
    >
      {error ? <ErrorNote error={error} /> : null}

      {!question && (
        <div className="flex flex-col gap-2">
          {!subjectId && <Empty>Choose a subject first.</Empty>}
          {topics.data?.length === 0 && (
            <Empty>No solved exam question is ready for this subject yet. They appear once a parent approves them.</Empty>
          )}
          {topics.data?.map((t) => (
            <button
              key={t.objective_id}
              onClick={() => void open(t)}
              className="flex flex-col items-start rounded-2xl border border-purple-200 bg-white px-3.5 py-2.5 text-left hover:bg-purple-50"
            >
              <span className="text-sm font-semibold text-slate-900">
                {t.code} {t.statement}
              </span>
              <span className="text-[11px] text-slate-500">
                {t.label} · {t.marks} marks · {t.steps} steps
              </span>
            </button>
          ))}
        </div>
      )}

      {question && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Chip tone="neutral">
              {question.label} · {question.marks} marks
            </Chip>
            <button onClick={() => setQuestion(null)} className="text-[11px] font-semibold text-purple-800 hover:underline">
              Choose another question
            </button>
          </div>
          {question.context && <MathText text={question.context} className="text-sm text-slate-700" />}
          <MathText text={question.stem} className="text-sm font-medium text-slate-900" />
          {question.has_diagram && (
            <p className="text-[11px] text-slate-500">In the paper this question comes with a graph.</p>
          )}

          {done.length > 0 && (
            <ol className="ml-5 list-decimal space-y-1.5 text-sm text-slate-700">
              {done.map((d, i) => (
                <li key={i}>
                  <span className="flex flex-wrap items-start gap-2">
                    <MathText text={d.text} className="flex-1" />
                    {d.mark && (
                      <span className="rounded-lg bg-indigo-100 px-1.5 py-0.5 text-[10px] font-bold text-indigo-800">
                        {d.mark}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}

          {!finished && !judged && (
            <div className="flex flex-col gap-2 rounded-2xl border border-purple-200 bg-purple-50/40 p-3">
              <label className="text-xs font-bold text-purple-900">
                Step {index} of {question.steps}: what would you write next, and why?
              </label>
              <textarea
                value={explanation}
                onChange={(e) => setExplanation(e.target.value)}
                maxLength={1500}
                rows={3}
                className="rounded-xl border border-purple-200 bg-white px-3 py-2 text-sm outline-none focus:border-purple-400"
                placeholder={voice === "recording" ? "Recording… tap ■ when you've finished" : "Explain your next step…"}
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={() => void defend()} disabled={busy || !explanation.trim()} className="h-8 px-3 text-xs">
                  {busy ? "Listening to your reasoning…" : "Defend this step"}
                </Button>
                <button
                  type="button"
                  onClick={() => void toggleVoice()}
                  disabled={voice === "transcribing"}
                  className="h-8 rounded-xl border border-purple-200 bg-white px-3 text-xs font-bold text-purple-800 hover:bg-purple-50 disabled:opacity-50"
                >
                  {voice === "recording" ? "■ Stop" : voice === "transcribing" ? "Writing it down…" : "🎙 Say it"}
                </button>
              </div>
            </div>
          )}

          {judged && (
            <div className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-3">
              <Chip tone={VERDICT[judged.verdict].tone}>{VERDICT[judged.verdict].label}</Chip>
              {judged.safety_message && <p className="text-sm text-slate-800">{judged.safety_message}</p>}
              {judged.what_was_right && <p className="text-sm text-emerald-800">✓ {judged.what_was_right}</p>}
              {judged.missing && <p className="text-sm text-amber-900">{judged.missing}</p>}
              {judged.hint && <p className="text-sm italic text-slate-700">Hint: {judged.hint}</p>}
              <div className="flex flex-wrap gap-2 pt-1">
                {judged.verdict !== "right" && judged.verdict !== "safety" && (
                  <Button variant="secondary" className="h-8 px-3 text-xs" onClick={() => setJudged(null)}>
                    Try again
                  </Button>
                )}
                {judged.verdict !== "safety" && (
                  <Button className="h-8 px-3 text-xs" onClick={showStep}>
                    {judged.verdict === "right" ? "See the step as written" : "Show me the step"}
                  </Button>
                )}
              </div>
            </div>
          )}

          {finished && (
            <p className="rounded-2xl bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              You&apos;ve been through every step. {done.filter((d) => d.verdict === "right").length} of {done.length}{" "}
              you explained before seeing them.
            </p>
          )}
        </div>
      )}
    </Card>
  );
}
