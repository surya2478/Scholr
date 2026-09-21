import Link from "next/link";
import type { Stream, SubjectCard } from "@/lib/api";
import { Chip } from "../ui";

// Streams and their subjects come from the API (subject configs); nothing here names a stream or subject.
const STAGE: Record<SubjectCard["stage"], { label: string; tone: "good" | "neutral" | "brand" }> = {
  taught: { label: "Taught here", tone: "good" },
  lessons: { label: "Lessons only", tone: "brand" },
  planned: { label: "Syllabus only", tone: "neutral" },
  external: { label: "Your coaching classes", tone: "brand" },
};

export function StageChip({ stage }: { stage: SubjectCard["stage"] }) {
  return <Chip tone={STAGE[stage].tone}>{STAGE[stage].label}</Chip>;
}

function SubjectTile({ subject }: { subject: SubjectCard }) {
  const progress =
    subject.secure === null
      ? `${subject.objectives} topics · not started`
      : `${subject.secure} of ${subject.objectives} topics secure · ${subject.practised} practised`;
  return (
    <Link
      href={`/student/learn/subject/${subject.id}`}
      className="flex flex-col gap-2 rounded-2xl border-2 border-amber-200/70 bg-white p-4 shadow-2xs transition hover:border-orange-300 hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-fun font-bold text-slate-900 leading-tight">{subject.name}</span>
        {subject.syllabus_code && <span className="text-[11px] font-semibold text-slate-400">{subject.syllabus_code}</span>}
      </div>
      <StageChip stage={subject.stage} />
      <span className="text-xs text-slate-500 font-medium">{progress}</span>
    </Link>
  );
}

export function StreamSection({ stream }: { stream: Stream }) {
  return (
    <section className="flex flex-col gap-3 rounded-3xl border-2 border-amber-200/80 bg-[#FFFDF9] p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-lg font-fun font-bold text-slate-900">{stream.name}</h2>
          <p className="text-xs text-slate-500 font-medium">{stream.description}</p>
        </div>
        {stream.status === "later" && <Chip tone="neutral">Coming later</Chip>}
      </div>
      {stream.status === "open" && stream.subjects.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {stream.subjects.map((subject) => (
            <SubjectTile key={subject.id} subject={subject} />
          ))}
        </div>
      )}
    </section>
  );
}

export function MasteryBadge({ level, name }: { level: number | null; name: string | null }) {
  if (level === null || name === null) return <span className="text-[11px] font-semibold text-slate-400">Not started</span>;
  const tone = level >= 3 ? "good" : level >= 2 ? "warn" : "neutral";
  return <Chip tone={tone}>{name}</Chip>;
}
