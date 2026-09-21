"use client";

// Small SVG charts for the parent dashboard. One series per chart, no second y-axis, recessive grid, and every
// chart carries its numbers in a table below it (the lightest fill is below 3:1 against white).
// Palette: one hue, three ordered steps, checked for colour-blind separation before use.
export const HELP_COLORS = ["#2f3dd1", "#6b7bf0", "#a3aef6"] as const;
const GRID = "#eceff6";
const AXIS_TEXT = "#8a91a6";

function Numbers({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <details className="text-[11px] text-muted">
      <summary className="cursor-pointer select-none font-semibold">Show the numbers</summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} className="pr-3 pb-1 font-semibold">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className="pr-3">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// Change over time, one series. Markers carry the value on hover; the last point is labelled.
export function TrendLine({
  points,
  labels,
  format,
  max,
  ariaLabel,
  unit = "",
}: {
  points: (number | null)[];
  labels: string[];
  format: (v: number) => string;
  max: number;
  ariaLabel: string;
  unit?: string;
}) {
  const width = 300;
  const height = 110;
  const pad = { left: 30, right: 22, top: 12, bottom: 18 };
  const top = max || 1;
  const x = (i: number) => pad.left + (i * (width - pad.left - pad.right)) / Math.max(1, points.length - 1);
  const y = (v: number) => height - pad.bottom - (v / top) * (height - pad.top - pad.bottom);
  const drawn = points.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v !== null);
  const path = drawn.map((p, n) => `${n === 0 ? "M" : "L"}${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const last = drawn.at(-1);

  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={ariaLabel}>
        {[0, top / 2, top].map((value) => (
          <g key={value}>
            <line x1={pad.left} x2={width - pad.right} y1={y(value)} y2={y(value)} stroke={GRID} strokeWidth="1" />
            <text x={pad.left - 6} y={y(value) + 3} textAnchor="end" fontSize="8" fill={AXIS_TEXT}>
              {format(value)}
            </text>
          </g>
        ))}
        {path && <path d={path} fill="none" stroke={HELP_COLORS[0]} strokeWidth="2" strokeLinejoin="round" />}
        {drawn.map((p) => (
          <circle key={p.i} cx={x(p.i)} cy={y(p.v)} r="4" fill="#ffffff" stroke={HELP_COLORS[0]} strokeWidth="2">
            <title>{`${labels[p.i]}: ${format(p.v)}${unit}`}</title>
          </circle>
        ))}
        {last && (
          // The newest value is labelled; it moves below its marker when the line is near the top of the plot.
          <text
            x={x(last.i) - 6}
            y={y(last.v) < pad.top + 12 ? y(last.v) + 14 : y(last.v) - 9}
            textAnchor="end"
            fontSize="9"
            fontWeight="700"
            fill="#1a2240"
          >
            {format(last.v)}
          </text>
        )}
        {[0, Math.floor((labels.length - 1) / 2), labels.length - 1].map((i) => (
          <text key={i} x={x(i)} y={height - 5} textAnchor="middle" fontSize="8" fill={AXIS_TEXT}>
            {labels[i]}
          </text>
        ))}
      </svg>
      <Numbers headers={["Week", ariaLabel]} rows={points.map((v, i) => [labels[i], v === null ? "—" : format(v)])} />
    </div>
  );
}

// How each week's answers were reached. Three ordered bands, stacked to the week's total, 2px gaps between them.
export function HelpMixBars({
  weeks,
  labels,
}: {
  weeks: { without_help: number; with_hints: number; worked_solution: number }[];
  labels: string[];
}) {
  const bands = [
    { key: "without_help", label: "Without help", color: HELP_COLORS[0] },
    { key: "with_hints", label: "With hints", color: HELP_COLORS[1] },
    { key: "worked_solution", label: "Worked solution", color: HELP_COLORS[2] },
  ] as const;
  const width = 300;
  const height = 110;
  const barWidth = Math.min(26, (width - 10) / Math.max(1, weeks.length) - 8);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        {bands.map((b) => (
          <span key={b.key} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: b.color }} />
            {b.label}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label="How answers were reached each week">
        {weeks.map((week, i) => {
          const total = week.without_help + week.with_hints + week.worked_solution;
          const step = (width - 10) / Math.max(1, weeks.length);
          const x = 5 + i * step + (step - barWidth) / 2;
          let cursor = height - 18;
          return (
            <g key={i}>
              {total === 0 ? (
                <rect x={x} y={height - 20} width={barWidth} height="2" rx="1" fill={GRID} />
              ) : (
                bands.map((band) => {
                  const value = week[band.key];
                  const barHeight = (value / total) * (height - 30);
                  cursor -= barHeight;
                  return value ? (
                    <rect key={band.key} x={x} y={cursor} width={barWidth} height={Math.max(0, barHeight - 2)} rx="3" fill={band.color}>
                      <title>{`${labels[i]} — ${band.label}: ${value} of ${total}`}</title>
                    </rect>
                  ) : null;
                })
              )}
              <text x={x + barWidth / 2} y={height - 5} textAnchor="middle" fontSize="8" fill={AXIS_TEXT}>
                {labels[i]}
              </text>
            </g>
          );
        })}
      </svg>
      <Numbers
        headers={["Week", "Without help", "With hints", "Worked solution"]}
        rows={weeks.map((w, i) => [labels[i], w.without_help, w.with_hints, w.worked_solution])}
      />
    </div>
  );
}

// Study minutes per day this week, against the family's own plan for an average day.
export function DayBars({ days, plannedPerDay }: { days: { day: string; study_minutes: number }[]; plannedPerDay: number }) {
  const width = 300;
  const height = 110;
  const top = Math.max(plannedPerDay, ...days.map((d) => d.study_minutes), 30) * 1.15;
  const step = (width - 10) / Math.max(1, days.length);
  const barWidth = Math.min(26, step - 8);
  const y = (v: number) => height - 20 - (v / top) * (height - 30);
  const label = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("en-GB", { weekday: "short" });

  return (
    <div className="flex flex-col gap-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label="Study time each day this week">
        {plannedPerDay > 0 && (
          <>
            <line x1="5" x2={width - 5} y1={y(plannedPerDay)} y2={y(plannedPerDay)} stroke={GRID} strokeWidth="1" strokeDasharray="4 3" />
            <text x={width - 5} y={y(plannedPerDay) - 3} textAnchor="end" fontSize="8" fill={AXIS_TEXT}>
              planned
            </text>
          </>
        )}
        {days.map((d, i) => {
          const x = 5 + i * step + (step - barWidth) / 2;
          const minutes = d.study_minutes;
          return (
            <g key={d.day}>
              <rect x={x} y={minutes ? y(minutes) : height - 22} width={barWidth} height={minutes ? height - 20 - y(minutes) : 2} rx="3" fill={minutes ? HELP_COLORS[1] : GRID}>
                <title>{`${label(d.day)}: ${minutes} min`}</title>
              </rect>
              <text x={x + barWidth / 2} y={height - 5} textAnchor="middle" fontSize="8" fill={AXIS_TEXT}>
                {label(d.day)}
              </text>
            </g>
          );
        })}
      </svg>
      <Numbers headers={["Day", "Minutes"]} rows={days.map((d) => [label(d.day), d.study_minutes])} />
    </div>
  );
}
