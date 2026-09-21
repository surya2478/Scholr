"use client";

import { useEffect, useState } from "react";
import type { Sitting } from "@/lib/api";
import { useApi } from "@/lib/useApi";

// The clock for a timed past-paper sitting (AC-R3). It counts down from the server's minutes-left and never cuts
// her off: running over is shown, and the server records it for the readiness view.
export function SittingClock({ assessmentId }: { assessmentId: string }) {
  const sitting = useApi<Sitting>(`/sittings/${assessmentId}`);
  const [now, setNow] = useState(() => Date.now());
  const [loadedAt, setLoadedAt] = useState(() => Date.now());

  useEffect(() => {
    if (sitting.data) setLoadedAt(Date.now());
  }, [sitting.data]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000);
    return () => window.clearInterval(timer);
  }, []);

  const data = sitting.data;
  if (!data || data.status !== "in_progress" || data.minutes_left === null || data.duration_min === null) return null;
  const elapsed = Math.floor((now - loadedAt) / 60_000);
  const left = data.minutes_left - elapsed;
  const over = left < 0 || data.over_time;

  return (
    <div
      className={`flex flex-wrap items-center gap-2 rounded-2xl border-2 px-4 py-2 text-sm font-fun font-bold ${
        over ? "border-rose-300 bg-rose-50 text-rose-800" : left <= 10 ? "border-amber-300 bg-amber-50 text-amber-900" : "border-blue-200 bg-blue-50 text-blue-900"
      }`}
      role="timer"
      aria-live="polite"
    >
      ⏱{" "}
      {over
        ? `Over time by ${Math.max(1, -left)} min — finish and submit; the overrun is noted.`
        : `${left} min left of ${data.duration_min}`}
    </div>
  );
}
