"use client";

import katex from "katex";
import { Fragment, useMemo } from "react";

// Renders text with $...$ (inline) and $$...$$ (display) LaTeX, as produced by OCR and the tutor.
const PATTERN = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g;

export function MathText({ text, className }: { text: string; className?: string }) {
  const parts = useMemo(() => text.split(PATTERN), [text]);
  return (
    <span className={className} style={{ whiteSpace: "pre-wrap" }}>
      {parts.map((part, i) => {
        const display = part.startsWith("$$") && part.endsWith("$$") && part.length > 4;
        const inline = !display && part.startsWith("$") && part.endsWith("$") && part.length > 2;
        if (!display && !inline) return <Fragment key={i}>{part}</Fragment>;
        const source = display ? part.slice(2, -2) : part.slice(1, -1);
        const html = katex.renderToString(source, { displayMode: display, throwOnError: false, output: "html" });
        return <span key={i} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </span>
  );
}
