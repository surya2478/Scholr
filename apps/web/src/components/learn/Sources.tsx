import type { SourceRef } from "@/lib/api";

// Where a piece of a lesson came from: her own book and the printed page, so she can look it up (AC-U4).
export function Sources({ sources }: { sources: SourceRef[] }) {
  if (sources.length === 0) return null;
  const byTitle = new Map<string, number[]>();
  for (const s of sources) {
    const pages = byTitle.get(s.title) ?? [];
    if (s.page !== null && !pages.includes(s.page)) pages.push(s.page);
    byTitle.set(s.title, pages);
  }
  return (
    <p className="text-[11px] text-slate-400 font-medium">
      📖{" "}
      {[...byTitle.entries()]
        .map(([title, pages]) => `${title}${pages.length ? `, p. ${pages.sort((a, b) => a - b).join(", ")}` : ""}`)
        .join(" · ")}
    </p>
  );
}
