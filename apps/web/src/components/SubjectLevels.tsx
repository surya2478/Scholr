import type { SubjectProgress } from "@/lib/api";
import { LEVELS } from "@/lib/format";

// Stacked bar of objectives per mastery level — counts, not percentages of "completion".
const COLORS = ["#e6eaf3", "#c7cff8", "#9aa8f3", "#4f6bed", "#2f3dd1", "#1a2598"];

export function SubjectLevels({ subject }: { subject: SubjectProgress }) {
  const total = subject.objectives_total || 1;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-semibold text-ink">{subject.subject_name}</span>
        <span className="text-xs text-muted">
          {subject.competent_or_better} of {subject.objectives_total} topics secure
        </span>
        {subject.retention_high > 0 && <span className="ml-auto text-[11px] text-warn">{subject.retention_high} review due</span>}
      </div>
      <div className="flex h-2.5 overflow-hidden rounded-full bg-[#e6eaf3]" role="img" aria-label={`${subject.subject_name} topic levels`}>
        {LEVELS.map((level, i) => {
          const n = subject.level_counts[level] ?? 0;
          return n ? <div key={level} title={`${level}: ${n}`} style={{ width: `${(n / total) * 100}%`, background: COLORS[i] }} className="border-r-2 border-white last:border-r-0" /> : null;
        })}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted">
        {LEVELS.map((level, i) =>
          subject.level_counts[level] ? (
            <span key={level} className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: COLORS[i] }} />
              {level} {subject.level_counts[level]}
            </span>
          ) : null,
        )}
      </div>
    </div>
  );
}
