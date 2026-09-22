"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { LessonDiagram } from "@/components/learn/diagrams/LessonDiagram";
import { ExploreWithAI } from "@/components/learn/ExploreWithAI";
import { ExternalLessonView } from "@/components/learn/ExternalLessonView";
import { FormulaDrawer } from "@/components/learn/FormulaDrawer";
import { LessonAudioPlayer } from "@/components/learn/LessonAudioPlayer";
import { Sources } from "@/components/learn/Sources";
import { MasteryBadge } from "@/components/learn/Streams";
import { DualLensView } from "@/components/learn/DualLensView";
import { DialecticalCrucible } from "@/components/learn/DialecticalCrucible";
import { InventingToLearn } from "@/components/learn/InventingToLearn";
import { ExamLevel } from "@/components/learn/ExamLevel";
import { TopicSteps } from "@/components/learn/TopicSteps";
import { TryQuestion } from "@/components/learn/TryQuestion";
import { WorkedExample } from "@/components/learn/WorkedExample";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type Lesson, type Topic } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

// Seconds on the page before the lesson counts as read (AC-U7: moves a topic to Introduced at most).
const READ_AFTER_S = 20;

function LessonView({
  objectiveId,
  lesson,
  askHref,
  read,
  explore,
}: {
  objectiveId: string;
  lesson: Lesson;
  askHref: ((q: string) => string) | null;
  read: boolean;
  // Present only where the Tutor can answer: it opens the Tutor on this section, in place.
  explore: { subjectId: string; objectiveId: string } | null;
}) {
  // A lesson she has already read opens as its summary, so the practice below it is a screen away rather than
  // three. The whole lesson is one tap back (docs/STUDENT-APP.md AC-U13).
  const [open, setOpen] = useState(!read);
  const [activeSectionIndex, setActiveSectionIndex] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <LessonAudioPlayer
        objectiveId={objectiveId}
        lesson={lesson}
        onSectionActive={(idx) => setActiveSectionIndex(idx)}
      />

      {lesson.summary && (
        <div className="rounded-2xl border border-orange-200 bg-orange-50/60 p-4 text-sm font-medium text-slate-800">
          <MathText text={lesson.summary} />
        </div>
      )}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="self-start rounded-xl border border-orange-200 bg-white px-3 py-1.5 text-xs font-fun font-bold text-orange-700 hover:bg-orange-50"
        >
          You&apos;ve read this before — read it again
        </button>
      )}
      {open && (
        <>
      {lesson.sections.map((section, i) => (
        <div
          key={i}
          className={`flex flex-col gap-1.5 transition-colors duration-300 rounded-xl p-2.5 ${
            activeSectionIndex === i ? "bg-orange-100/70 border border-orange-300 shadow-2xs" : ""
          }`}
        >
          <h3 className="font-fun font-bold text-slate-900">{section.heading}</h3>
          <MathText text={section.body} className="text-sm leading-relaxed text-slate-700" />
          <Sources sources={section.sources} />
          {explore && (
            <ExploreWithAI
              subjectId={explore.subjectId}
              objectiveId={explore.objectiveId}
              heading={section.heading}
              question={`Tell me more about "${section.heading}" in this topic, with an example.`}
            />
          )}
        </div>
      ))}
      {lesson.diagrams.map((diagram, i) => (
        <LessonDiagram key={i} diagram={diagram} />
      ))}
      {lesson.key_terms.length > 0 && (
        <div className="rounded-2xl border border-blue-200 bg-blue-50/50 p-4">
          <h3 className="mb-2 font-fun font-bold text-blue-900">Key terms</h3>
          <dl className="flex flex-col gap-1.5 text-sm">
            {lesson.key_terms.map((t, i) => (
              <div key={i}>
                <dt className="inline font-semibold text-slate-900">{t.term}: </dt>
                <dd className="inline text-slate-700">
                  <MathText text={t.meaning} />
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
      {lesson.worked_examples.map((ex, i) => (
        <WorkedExample key={i} example={ex} index={i} askHref={askHref} />
      ))}
      {lesson.pitfalls.length > 0 && (
        <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4">
          <h3 className="mb-2 font-fun font-bold text-amber-900">Watch out for</h3>
          <ul className="ml-5 list-disc space-y-1 text-sm text-slate-700">
            {lesson.pitfalls.map((p, i) => (
              <li key={i}>
                <MathText text={p} />
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-[11px] text-slate-400">{lesson.note}</p>
        </>
      )}
    </div>
  );
}

export default function TopicPage() {
  const { id } = useParams<{ id: string }>();
  const topic = useApi<Topic>(`/learn/objectives/${id}`);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const data = topic.data;
  const lesson = data?.lesson ?? null;

  const askHref = (q: string) =>
    tutorHref({ subjectId: data?.subject.id ?? "", objectiveId: id, about: data?.objective.statement, ask: q });

  useEffect(() => {
    if (lesson?.status !== "ready") return;
    const timer = window.setTimeout(() => {
      api(`/learn/objectives/${id}/read`, { method: "POST" }).catch(() => undefined);
    }, READ_AFTER_S * 1000);
    return () => window.clearTimeout(timer);
  }, [id, lesson?.status]);

  async function writeLesson() {
    setWriting(true);
    setError(null);
    try {
      const written = await api<Lesson>(`/learn/objectives/${id}/lesson`, { method: "POST" });
      topic.setData((prev) => (prev ? { ...prev, lesson: written } : prev));
    } catch (err) {
      setError(err);
    } finally {
      setWriting(false);
    }
  }

  return (
    <div className="space-y-5">
      {data && (
        <Link href={`/student/learn/subject/${data.subject.id}`} className="text-xs font-bold text-orange-600 hover:underline">
          ← {data.subject.name}
        </Link>
      )}
      {topic.error ? <ErrorNote error={topic.error} /> : null}
      {topic.loading && <p className="text-sm text-slate-500">Loading the topic…</p>}
      {data && (
        <>
          <div className="flex flex-col gap-2">
            <p className="text-xs font-semibold text-slate-500">{data.path.join(" › ")}</p>
            <h1 className="text-2xl font-fun font-bold text-slate-900">
              <span className="mr-2 text-slate-400">{data.objective.code}</span>
              {data.objective.statement}
            </h1>
            <div className="flex flex-wrap items-center gap-2">
              {data.subject.stage !== "external" && (
                <MasteryBadge level={data.objective.mastery_level} name={data.objective.mastery_name} />
              )}
              {data.tutor_available && (
                <Link
                  href={askHref("I have a doubt about this topic.")}
                  className="rounded-xl border border-orange-200 bg-white px-3 py-1 text-xs font-fun font-bold text-orange-700 hover:bg-orange-50"
                >
                  🦉 Ask a doubt
                </Link>
              )}
            </div>
          </div>

          <TopicSteps
            steps={data.steps}
            minutes={data.minutes}
            links={[
              ...(data.exam_level ? [{ key: "exam-level", label: "🎯 Exam level" }] : []),
              ...(data.tutor_available ? [{ key: "mistakes", label: "🔁 Your mistakes" }] : []),
            ]}
          />

          {data.notice && <Empty>{data.notice}</Empty>}

          {data.external && (
            <ExternalLessonView
              lesson={data.external}
              subjectId={data.subject.id}
              objectiveId={data.objective.id}
              title={data.objective.statement}
              onChanged={() => void topic.reload()}
            />
          )}

          {data.lesson_available && (
            <section id="part-lesson" className="scroll-mt-24">
            <Card title="📘 Learn" subtitle="Scholr's lesson, written from your course books" tone="orange">
              {error ? <ErrorNote error={error} /> : null}
              {!lesson && (
                <div className="flex flex-col items-start gap-2">
                  <p className="text-sm text-slate-600">No lesson has been written for this topic yet.</p>
                  <Button onClick={writeLesson} disabled={writing}>
                    {writing ? "Writing from your books… (about 20 s)" : "Write this lesson"}
                  </Button>
                </div>
              )}
              {lesson?.status === "not_enough_material" && (
                <Empty>
                  Your course books don&apos;t cover this topic well enough for Scholr to write a lesson it can stand behind.
                  Try the questions below, or ask the Tutor.
                </Empty>
              )}
              {lesson?.status === "ready" && (
                <LessonView
                  objectiveId={id}
                  lesson={lesson}
                  askHref={data.tutor_available ? askHref : null}
                  read={data.steps.some((s) => s.key === "lesson" && s.done)}
                  explore={
                    data.tutor_available ? { subjectId: data.subject.id, objectiveId: data.objective.id } : null
                  }
                />
              )}
            </Card>
            </section>
          )}

          {data.exam_level && (
            <section id="part-exam-level" className="scroll-mt-24">
              <Card
                title="🎯 Exam level"
                subtitle="How the exam asks about this topic, and a real question solved to full marks"
                tone="purple"
              >
                <ExamLevel data={data.exam_level} askHref={data.tutor_available ? askHref : null} />
              </Card>
            </section>
          )}

          {/* Every part of a taught topic is always on the page, empty or not: a part that hides itself when it
              has nothing reads as a feature that does not exist. */}
          {data.tutor_available && (
            <section id="part-check" className="scroll-mt-24">
              <Card title="✅ Check yourself" subtitle="Short questions, marked straight away" tone="emerald">
                {data.check_yourself.length === 0 && <Empty>No questions for this topic in the bank yet.</Empty>}
                {data.check_yourself.map((item, idx) => (
                  <TryQuestion key={item.id} item={item} askHref={askHref} startOpen={idx === 0} />
                ))}
              </Card>
            </section>
          )}

          {data.tutor_available && (
            <section id="part-exam" className="scroll-mt-24">
              <Card
                title="📝 Exam questions"
                subtitle="Real Cambridge past-paper questions on this topic. After marking you'll see what examiners said."
                tone="blue"
              >
                {data.exam_questions.length === 0 && (
                  <Empty>No past-paper question on this topic has been added to the bank yet.</Empty>
                )}
                {data.exam_questions.map((item) => (
                  <TryQuestion key={item.id} item={item} askHref={askHref} />
                ))}
              </Card>
            </section>
          )}

          {data.tutor_available && (
            <section id="part-mistakes" className="scroll-mt-24">
              <Card title="🔁 Your mistakes here" subtitle="Patterns from your own marked answers" tone="amber">
                {data.mistakes.length === 0 && (
                  <Empty>Nothing recorded on this topic yet — mistakes appear here after your answers are marked.</Empty>
                )}
                <ul className="flex flex-col gap-2">
                  {data.mistakes.map((m, i) => (
                    <li key={i} className="flex items-start justify-between gap-3 text-sm text-slate-700">
                      <MathText text={m.description} />
                      <Chip tone={m.status === "open" ? "warn" : "good"}>
                        {m.occurrences}× · {m.status}
                      </Chip>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          )}

          <DualLensView subject={data.subject} objective={data.objective} connections={data.connections} />

          {data.subject.name.toLowerCase().includes("sociology") && (
            <DialecticalCrucible unitName={data.path[0]} />
          )}

          {data.connections.length > 0 && !data.connections.some((c) => c.subject_name.toLowerCase().includes("iit")) && (
            <Card title="🔗 Connections" subtitle="The same idea in your other subjects" tone="purple">
              <ul className="flex flex-col gap-2">
                {data.connections.map((c) => (
                  <li key={c.objective_id}>
                    <Link
                      href={`/student/learn/topic/${c.objective_id}`}
                      className="flex flex-col rounded-xl px-2 py-1.5 hover:bg-purple-50"
                    >
                      <span className="text-sm font-semibold text-slate-900">
                        {c.subject_name} · {c.objective_code} {c.statement}
                      </span>
                      <span className="text-xs text-slate-500">Shared idea: {c.concept}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <InventingToLearn />

          <FormulaDrawer lesson={lesson} />
        </>
      )}
    </div>
  );
}
