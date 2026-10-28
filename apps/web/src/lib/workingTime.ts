"use client";

import { useCallback, useEffect, useRef } from "react";

// Time she spends on one question: from her first touch of it (not from when the page opened, since a test shows
// every question at once) and only while the page is on screen. Sent with the answer as time_spent_s; null if she
// never touched the question, so nothing is guessed.
export function useWorkingTime(): { begin: () => void; seconds: () => number | null } {
  const spent = useRef(0); // milliseconds counted so far
  const since = useRef<number | null>(null); // when the current visible stretch began
  const started = useRef(false);

  useEffect(() => {
    const onVisibility = () => {
      if (!started.current) return;
      if (document.hidden && since.current !== null) {
        spent.current += Date.now() - since.current;
        since.current = null;
      } else if (!document.hidden && since.current === null) {
        since.current = Date.now();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const begin = useCallback(() => {
    if (started.current) return;
    started.current = true;
    since.current = document.hidden ? null : Date.now();
  }, []);

  const seconds = useCallback(() => {
    if (!started.current) return null;
    const total = spent.current + (since.current !== null ? Date.now() - since.current : 0);
    return Math.max(1, Math.round(total / 1000));
  }, []);

  return { begin, seconds };
}
