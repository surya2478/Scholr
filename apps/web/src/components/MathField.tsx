"use client";

import { useEffect, useRef, useState } from "react";

type Field = HTMLElement & { value: string; mathVirtualKeyboardPolicy: string };

// MathLive maths input (typed answers arrive as LaTeX, ARCHITECTURE §11). It loads in the browser only; if it cannot
// load, a plain text box keeps the answer box usable. The on-screen maths keyboard opens on touch devices.
export function MathField({
  value,
  onChange,
  label,
  className = "",
}: {
  value: string;
  onChange: (latex: string) => void;
  label: string;
  className?: string;
}) {
  const host = useRef<HTMLDivElement>(null);
  const field = useRef<Field | null>(null);
  const changed = useRef(onChange);
  const initial = useRef(value);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    changed.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let cancelled = false;
    const container = host.current;
    import("mathlive")
      .then(({ MathfieldElement }) => {
        if (cancelled || !container) return;
        MathfieldElement.fontsDirectory = null; // KaTeX fonts come with the app's KaTeX stylesheet
        MathfieldElement.soundsDirectory = null;
        const el = new MathfieldElement() as unknown as Field;
        el.mathVirtualKeyboardPolicy = "auto";
        el.setAttribute("aria-label", label);
        el.value = initial.current;
        el.style.width = "100%";
        el.style.fontSize = "1.05rem";
        el.addEventListener("input", () => changed.current(el.value));
        container.replaceChildren(el);
        field.current = el;
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      field.current = null;
      container?.replaceChildren();
    };
  }, [label]);

  useEffect(() => {
    if (field.current && field.current.value !== value) field.current.value = value;
  }, [value]);

  if (failed) {
    return (
      <input
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`h-10 rounded-xl border border-line bg-white px-3 text-sm font-normal ${className}`}
      />
    );
  }
  return <div ref={host} className={`min-h-10 rounded-xl border border-line bg-white px-2 py-1 ${className}`} />;
}
