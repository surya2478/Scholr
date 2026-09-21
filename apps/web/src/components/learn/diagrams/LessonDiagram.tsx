import type { Lesson } from "@/lib/api";
import { DIAGRAMS } from "./shapes";

// One diagram beside its lesson (docs/STUDENT-APP.md AC-U14). Everything drawn was computed and checked by the
// API; an unknown kind draws nothing rather than guessing.
export function LessonDiagram({ diagram }: { diagram: Lesson["diagrams"][number] }) {
  const Shape = DIAGRAMS[diagram.kind];
  if (!Shape) return null;
  return (
    <figure className="flex flex-col items-center gap-2 rounded-2xl border border-violet-200 bg-violet-50/40 p-4">
      <Shape data={diagram.data} />
      <figcaption className="text-center text-xs text-slate-600">{diagram.caption}</figcaption>
    </figure>
  );
}
