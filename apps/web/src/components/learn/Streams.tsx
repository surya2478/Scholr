import Link from "next/link";
import type { Stream, SubjectCard } from "@/lib/api";
import { Chip } from "../ui";

// Streams and their subjects come from the API (subject configs); nothing here names a stream or subject.
const STAGE: Record<SubjectCard["stage"], { label: string; tone: "good" | "neutral" | "brand" }> = {
  taught: { label: "Full Course & Marking", tone: "good" },
  lessons: { label: "Revision Notes & Tutor", tone: "brand" },
  planned: { label: "Syllabus Mapped", tone: "neutral" },
  external: { label: "IIT Coaching Bridge", tone: "brand" },
};

export function StageChip({ stage }: { stage: SubjectCard["stage"] }) {
  return <Chip tone={STAGE[stage].tone}>{STAGE[stage].label}</Chip>;
}

function SubjectTile({ subject }: { subject: SubjectCard }) {
  const pct =
    subject.secure !== null && subject.objectives > 0
      ? Math.round((subject.secure / subject.objectives) * 100)
      : subject.practised > 0 && subject.objectives > 0
      ? Math.round((subject.practised / subject.objectives) * 100)
      : 0;

  const progress =
    subject.secure === null
      ? `${subject.objectives} syllabus topics ready`
      : `${subject.secure} of ${subject.objectives} secure · ${subject.practised} practised`;

  return (
    <Link
      href={`/student/learn/subject/${subject.id}`}
      className="group flex flex-col justify-between gap-3 rounded-2xl border border-slate-200/90 bg-white p-4.5 shadow-2xs transition-all hover:border-blue-500 hover:shadow-md"
    >
      <div className="space-y-2.5">
        <div className="flex items-start justify-between gap-2">
          <span className="text-base font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors leading-tight">
            {subject.name}
          </span>
          {subject.syllabus_code && (
            <span className="rounded-md bg-slate-900 px-2 py-0.5 font-mono text-[11px] font-bold text-white shrink-0">
              {subject.syllabus_code}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <StageChip stage={subject.stage} />
        </div>
      </div>

      <div className="space-y-2 pt-1 border-t border-slate-100">
        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500 font-medium">{progress}</span>
          {pct > 0 && <span className="font-mono font-bold text-emerald-600">{pct}%</span>}
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all"
            style={{ width: `${Math.max(pct, subject.stage === "taught" || subject.stage === "lessons" ? 6 : 0)}%` }}
          />
        </div>
      </div>
    </Link>
  );
}

export function StreamSection({ stream }: { stream: Stream }) {
  return (
    <section className="flex flex-col gap-3.5 rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-100 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-600" />
            <h2 className="text-base md:text-lg font-extrabold text-slate-900">{stream.name}</h2>
          </div>
          <p className="text-xs text-slate-500 font-medium pl-4">{stream.description}</p>
        </div>
        {stream.status === "later" && <Chip tone="neutral">Scheduled Later</Chip>}
      </div>
      {stream.status === "open" && stream.subjects.length > 0 && (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {stream.subjects.map((subject) => (
            <SubjectTile key={subject.id} subject={subject} />
          ))}
        </div>
      )}
    </section>
  );
}

export function MasteryBadge({ level, name }: { level: number | null; name: string | null }) {
  if (level === null || name === null)
    return <span className="font-mono text-[11px] font-semibold text-slate-400">UNSTARTED</span>;
  const tone = level >= 3 ? "good" : level >= 2 ? "warn" : "neutral";
  return <Chip tone={tone}>{name}</Chip>;
}
