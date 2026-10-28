"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ActiveRecallDeck } from "@/components/learn/ActiveRecallDeck";
import { DialecticalCrucible } from "@/components/learn/DialecticalCrucible";
import { DualLensView } from "@/components/learn/DualLensView";
import { ExamLevel } from "@/components/learn/ExamLevel";
import { ExternalLessonView } from "@/components/learn/ExternalLessonView";
import { FormulaDrawer } from "@/components/learn/FormulaDrawer";
import { InventingToLearn } from "@/components/learn/InventingToLearn";
import { LessonAudioPlayer } from "@/components/learn/LessonAudioPlayer";
import { LessonNotes } from "@/components/learn/LessonNotes";
import { TopicQuestions } from "@/components/learn/TopicQuestions";
import { MasteryBadge } from "@/components/learn/Streams";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type Chapter, type Lesson, type ObjectiveCard, type SubjectLearn, type Topic } from "@/lib/api";
import { tutorHref } from "@/lib/tutor";
import { useApi } from "@/lib/useApi";

// Seconds on the page before the lesson counts as read (AC-U7: moves a topic to Introduced at most).
const READ_AFTER_S = 20;

type StudyTab = "notes" | "questions" | "flashcards" | "walkthrough" | "all";

type Neighbour = { id: string; code: string; statement: string };
type Place = { chapter: string; index: number; count: number; prev: Neighbour | null; next: Neighbour | null };

function chapterObjectives(chapter: Chapter): ObjectiveCard[] {
  return [...chapter.objectives, ...chapter.chapters.flatMap(chapterObjectives)];
}

// Where this topic sits in its subject, in the order the subject page lists topics: its chapter, its number in
// that chapter, and the topics either side (which may be in the next or previous chapter).
function placeOf(view: SubjectLearn | null | undefined, objectiveId: string): Place | null {
  if (!view) return null;
  const order: { o: ObjectiveCard; chapter: Chapter }[] = view.chapters.flatMap((chapter) =>
    chapterObjectives(chapter).map((o) => ({ o, chapter })),
  );
  const at = order.findIndex((x) => x.o.id === objectiveId);
  if (at < 0) return null;
  const chapter = order[at].chapter;
  const inChapter = order.filter((x) => x.chapter.id === chapter.id);
  const near = (x: { o: ObjectiveCard } | undefined): Neighbour | null =>
    x ? { id: x.o.id, code: x.o.code, statement: x.o.statement } : null;
  return {
    chapter: chapter.code ? `${chapter.code} ${chapter.name}` : chapter.name,
    index: inChapter.findIndex((x) => x.o.id === objectiveId) + 1,
    count: inChapter.length,
    prev: near(order[at - 1]),
    next: near(order[at + 1]),
  };
}

function LessonView({
  objectiveId,
  lesson,
  askHref,
  explore,
  onStartQuestions,
  hasQuestions,
  next,
}: {
  objectiveId: string;
  lesson: Lesson;
  askHref: ((q: string) => string) | null;
  explore: { subjectId: string; objectiveId: string } | null;
  onStartQuestions?: () => void;
  hasQuestions?: boolean;
  next: Neighbour | null;
}) {
  const [activeSectionIndex, setActiveSectionIndex] = useState<number | null>(null);
  const [listening, setListening] = useState(false);
  const [readCount, setReadCount] = useState({ read: 0, total: lesson.sections.length });
  const onReadCountChange = useCallback((read: number, total: number) => setReadCount({ read, total }), []);

  return (
    <div className="flex flex-col gap-4">
      {lesson.summary && (
        <div className="max-w-prose rounded-xl border-l-4 border-l-blue-600 bg-blue-50/50 px-4 py-3 text-[15px] font-medium leading-relaxed text-slate-800">
          <div className="mb-0.5 text-[11px] font-bold uppercase tracking-wider text-blue-900">📌 In one line</div>
          <MathText text={lesson.summary} />
        </div>
      )}

      {/* The voice and podcast stay one tap away instead of sitting above the notes */}
      <div>
        <button
          type="button"
          onClick={() => setListening((v) => !v)}
          className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
            listening ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          }`}
        >
          🎧 {listening ? "Hide audio" : "Listen to this lesson"}
        </button>
        {listening && (
          <div className="mt-3">
            <LessonAudioPlayer
              objectiveId={objectiveId}
              lesson={lesson}
              onSectionActive={(idx) => setActiveSectionIndex(idx)}
            />
          </div>
        )}
      </div>

      <LessonNotes
        objectiveId={objectiveId}
        lesson={lesson}
        askHref={askHref}
        explore={explore}
        activeSectionIndex={activeSectionIndex}
        onReadCountChange={onReadCountChange}
      />

      {/* One clear next step at the end of the notes */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <div className="space-y-0.5">
          <p className="text-sm font-bold text-slate-900">
            {readCount.total > 0 && readCount.read >= readCount.total
              ? "All sections read — now check you can use it."
              : `You've ticked ${readCount.read} of ${readCount.total} sections as read.`}
          </p>
          <p className="text-xs text-slate-600">
            {hasQuestions
              ? "Start with the Easy questions; they are marked as soon as you answer."
              : next
              ? "No questions are set on this topic yet — carry on to the next topic."
              : "That's the last topic in this subject."}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {hasQuestions && onStartQuestions && (
            <button
              type="button"
              onClick={onStartQuestions}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-500 cursor-pointer transition"
            >
              ✍️ Try the Easy questions →
            </button>
          )}
          {next && (
            <Link
              href={`/student/learn/topic/${next.id}`}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-800 hover:bg-slate-100 transition"
            >
              Next topic: {next.code} →
            </Link>
          )}
        </div>
      </div>

      <p className="text-[11px] text-slate-400">{lesson.note}</p>
    </div>
  );
}

export default function TopicPage() {
  const { id } = useParams<{ id: string }>();
  const topic = useApi<Topic>(`/learn/objectives/${id}`);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [activeTab, setActiveTab] = useState<StudyTab>("notes");

  const data = topic.data;
  const lesson = data?.lesson ?? null;
  const subjectView = useApi<SubjectLearn>(data ? `/learn/subjects/${data.subject.id}` : null);
  const place = useMemo(() => placeOf(subjectView.data, id), [subjectView.data, id]);

  const askHref = (q: string) =>
    tutorHref({ subjectId: data?.subject.id ?? "", objectiveId: id, about: data?.objective.statement, ask: q });

  // Detect the URL hash (#easy-1, #easy-2, #medium-1, #hard-1, #questions, #flashcards) to switch tabs
  useEffect(() => {
    function checkHash() {
      const hash = window.location.hash.replace(/^#/, "").toLowerCase();
      if (
        hash.startsWith("easy-") ||
        hash.startsWith("medium-") ||
        hash.startsWith("hard-") ||
        hash === "questions" ||
        hash === "part-exam" ||
        hash === "part-check"
      ) {
        setActiveTab("questions");
      } else if (hash === "flashcards" || hash === "part-recall") {
        setActiveTab("flashcards");
      } else if (hash === "walkthrough" || hash === "part-exam-level") {
        setActiveTab("walkthrough");
      } else {
        setActiveTab("notes");
      }
    }
    checkHash();
    window.addEventListener("hashchange", checkHash);
    return () => window.removeEventListener("hashchange", checkHash);
  }, [id]);

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

  function openTab(tab: StudyTab, hash: string) {
    setActiveTab(tab);
    window.history.replaceState(null, "", `#${hash}`);
  }

  function startQuestions() {
    openTab("questions", "easy-1");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const bankIds = new Set<string>();
  if (data) {
    for (const c of [...data.check_yourself, ...data.exam_questions]) {
      bankIds.add(c.id);
    }
  }
  const totalQuestionCount =
    bankIds.size +
    (lesson?.worked_examples?.length ?? 0) +
    (lesson?.exam_answers?.length ?? 0);

  const tabClass = (active: boolean) =>
    `flex flex-none items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition cursor-pointer ${
      active ? "bg-slate-900 text-white shadow-2xs" : "bg-slate-100 text-slate-700 hover:bg-slate-200/80"
    }`;

  // The server's own breakdown of this page: Learn → Check yourself → Exam questions, with minutes and done.
  const STEP_TAB: Record<string, { tab: StudyTab; hash: string }> = {
    lesson: { tab: "notes", hash: "notes" },
    check: { tab: "questions", hash: "easy-1" },
    exam: { tab: "questions", hash: "questions" },
  };

  return (
    <div className="space-y-5">
      {topic.error ? <ErrorNote error={topic.error} /> : null}
      {topic.loading && <p className="text-sm text-slate-500">Loading topic…</p>}
      {data && (
        <>
          {/* Breadcrumb and topic header */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 md:p-6 shadow-2xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-semibold text-slate-500">
              <div className="flex flex-wrap items-center gap-1.5">
                <Link href="/student/learn" className="text-blue-700 hover:underline font-bold">
                  IGCSE
                </Link>
                <span>›</span>
                <Link href={`/student/learn/subject/${data.subject.id}`} className="text-blue-700 hover:underline font-bold">
                  {data.subject.name}
                </Link>
                {data.subject.syllabus_code && (
                  <>
                    <span>›</span>
                    <span className="text-slate-600">CIE ({data.subject.syllabus_code})</span>
                  </>
                )}
                {data.path.map((segment, i) => (
                  <span key={i} className="flex items-center gap-1.5">
                    <span>›</span>
                    <span>{segment}</span>
                  </span>
                ))}
              </div>

              <div className="flex items-center gap-2">
                {place && (
                  <span className="rounded-lg bg-slate-100 px-2.5 py-1 font-mono text-[11px] font-bold text-slate-700">
                    Topic {place.index} of {place.count} in this chapter
                  </span>
                )}
                {data.tutor_available && (
                  <Link
                    href={askHref("I have a doubt about this topic.")}
                    className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-800 hover:bg-blue-100 transition"
                  >
                    🤖 Ask the AI Mentor
                  </Link>
                )}
              </div>
            </div>

            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-1.5">
                <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-slate-900">
                  <span className="mr-2.5 rounded-lg bg-slate-900 px-2.5 py-1 align-middle font-mono text-base text-white">
                    {data.objective.code}
                  </span>
                  {data.objective.statement}
                </h1>
                <p className="text-xs font-medium text-slate-500">
                  Cambridge (CIE) IGCSE {data.subject.name}
                  {data.subject.syllabus_code ? ` · Syllabus ${data.subject.syllabus_code}` : ""}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {data.subject.stage !== "external" && (
                  <MasteryBadge level={data.objective.mastery_level} name={data.objective.mastery_name} />
                )}
                {data.minutes > 0 && (
                  <span className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
                    ⏱️ ~{data.minutes} min
                  </span>
                )}
              </div>
            </div>

            {/* Path through this topic, from the server's steps */}
            {data.subject.stage !== "external" && data.steps.length > 0 && (
              <ol className="flex flex-wrap items-stretch gap-2">
                {data.steps.map((step, i) => {
                  const target = STEP_TAB[step.key];
                  return (
                    <li key={step.key} className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={!target}
                        onClick={() => target && openTab(target.tab, target.hash)}
                        className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-left text-xs transition cursor-pointer disabled:cursor-default ${
                          step.done
                            ? "border-emerald-300 bg-emerald-50 text-emerald-900"
                            : "border-slate-200 bg-white text-slate-800 hover:border-blue-400"
                        }`}
                      >
                        <span
                          className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                            step.done ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-700"
                          }`}
                        >
                          {step.done ? "✓" : i + 1}
                        </span>
                        <span className="font-bold">{step.label}</span>
                        <span className="font-mono text-[11px] text-slate-500">{step.minutes} min</span>
                      </button>
                      {i < data.steps.length - 1 && <span className="text-slate-300">→</span>}
                    </li>
                  );
                })}
              </ol>
            )}

            {/* Study-mode tabs: one row that scrolls sideways on a phone */}
            {data.subject.stage !== "external" && (
              <div className="-mx-1 flex items-center gap-2 overflow-x-auto border-t border-slate-100 px-1 pt-3.5">
                <button type="button" onClick={() => openTab("notes", "notes")} className={tabClass(activeTab === "notes")}>
                  📖 Revision Notes
                </button>

                {data.subject.stage === "taught" && (
                  <button
                    type="button"
                    onClick={() => {
                      setActiveTab("questions");
                      if (!window.location.hash.match(/^#(easy|medium|hard)-\d+$/)) {
                        window.history.replaceState(null, "", "#easy-1");
                      }
                    }}
                    className={tabClass(activeTab === "questions")}
                  >
                    ✍️ Topic Questions
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] ${
                        activeTab === "questions" ? "bg-white/20 text-white" : "bg-slate-200 text-slate-800"
                      }`}
                    >
                      {totalQuestionCount}
                    </span>
                  </button>
                )}

                {lesson?.status === "ready" && (
                  <button
                    type="button"
                    onClick={() => openTab("flashcards", "flashcards")}
                    className={tabClass(activeTab === "flashcards")}
                  >
                    🗂️ Flashcards
                  </button>
                )}

                {(data.exam_level || data.crucible) && (
                  <button
                    type="button"
                    onClick={() => openTab("walkthrough", "walkthrough")}
                    className={tabClass(activeTab === "walkthrough")}
                  >
                    🎯 Exam Walkthrough{data.crucible ? " & Crucible" : ""}
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => openTab("all", "all")}
                  className={`ml-auto flex flex-none items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition cursor-pointer ${
                    activeTab === "all" ? "bg-slate-800 text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                  }`}
                >
                  📋 Everything on one page
                </button>
              </div>
            )}
          </div>

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

          {/* TAB 1: REVISION NOTES */}
          {(activeTab === "notes" || activeTab === "all") && data.lesson_available && (
            <section id="part-lesson" className="scroll-mt-24 space-y-5">
              <Card>
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
                    Try the Topic Questions tab above, or ask the AI Mentor.
                  </Empty>
                )}
                {lesson?.status === "ready" && (
                  <LessonView
                    objectiveId={id}
                    lesson={lesson}
                    askHref={data.tutor_available ? askHref : null}
                    explore={
                      data.tutor_available ? { subjectId: data.subject.id, objectiveId: data.objective.id } : null
                    }
                    hasQuestions={data.subject.stage === "taught" && totalQuestionCount > 0}
                    onStartQuestions={startQuestions}
                    next={place?.next ?? null}
                  />
                )}
              </Card>

              <DualLensView
                subject={data.subject}
                objective={data.objective}
                connections={data.connections}
                lesson={lesson}
                examLevel={data.exam_level}
              />
            </section>
          )}

          {/* TAB 2: TOPIC QUESTIONS (Easy / Medium / Hard + #easy-1, #easy-2...) */}
          {(activeTab === "questions" || activeTab === "all") && data.subject.stage === "taught" && (
            <section id="part-questions" className="scroll-mt-24 space-y-5">
              <TopicQuestions
                topicName={data.objective.statement}
                topicCode={data.objective.code}
                subjectName={data.subject.name}
                subjectCode={data.subject.code}
                syllabusCode={data.subject.syllabus_code}
                checkYourself={data.check_yourself}
                examQuestions={data.exam_questions}
                lesson={lesson}
                askHref={askHref}
                onQuestionAnswered={() => void topic.reload()}
              />

              {data.mistakes.length > 0 && (
                <Card title="🔁 Your Recorded Mistakes on This Topic" subtitle="Patterns from your marked answers" tone="amber">
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
              )}
            </section>
          )}

          {/* TAB 3: FLASHCARDS & ACTIVE RECALL */}
          {(activeTab === "flashcards" || activeTab === "all") && lesson?.status === "ready" && (
            <section id="part-recall" className="scroll-mt-24">
              <ActiveRecallDeck lesson={lesson} />
            </section>
          )}

          {/* TAB 4: EXAM WALKTHROUGH & CRUCIBLE */}
          {(activeTab === "walkthrough" || activeTab === "all") && (
            <section id="part-exam-level" className="scroll-mt-24 space-y-5">
              {data.exam_level && (
                <Card
                  title="🎯 Exam Level & Official Past-Paper Walkthrough"
                  subtitle="How Cambridge examines this topic, and a real past-paper question solved step-by-step"
                  tone="purple"
                >
                  <ExamLevel data={data.exam_level} askHref={data.tutor_available ? askHref : null} />
                </Card>
              )}

              {data.crucible && <DialecticalCrucible crucible={data.crucible} />}

              <InventingToLearn statement={data.objective.statement} />
            </section>
          )}

          {data.connections.length > 0 && !data.connections.some((c) => c.subject_name.toLowerCase().includes("iit")) && (
            <Card title="🔗 Cross-Subject Connections" subtitle="The same concept in your other subjects" tone="purple">
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

          {/* Previous / next topic, in the subject's own order */}
          {place && (place.prev || place.next) && (
            <nav className="grid grid-cols-1 gap-3 sm:grid-cols-2" aria-label="Topic navigation">
              {place.prev ? (
                <Link
                  href={`/student/learn/topic/${place.prev.id}`}
                  className="group rounded-2xl border border-slate-200 bg-white p-4 hover:border-blue-400 transition"
                >
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">← Previous topic</div>
                  <div className="mt-1 text-sm font-bold text-slate-900 group-hover:text-blue-700">
                    <span className="font-mono">{place.prev.code}</span> {place.prev.statement}
                  </div>
                </Link>
              ) : (
                <span />
              )}
              {place.next && (
                <Link
                  href={`/student/learn/topic/${place.next.id}`}
                  className="group rounded-2xl border border-slate-200 bg-white p-4 text-right hover:border-blue-400 transition"
                >
                  <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Next topic →</div>
                  <div className="mt-1 text-sm font-bold text-slate-900 group-hover:text-blue-700">
                    <span className="font-mono">{place.next.code}</span> {place.next.statement}
                  </div>
                </Link>
              )}
            </nav>
          )}

          <FormulaDrawer lesson={lesson} />
        </>
      )}
    </div>
  );
}
