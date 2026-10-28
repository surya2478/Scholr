// The pictures a lesson can carry (docs/STUDENT-APP.md AC-U14). Each one draws exactly what the API's check
// computed — the prime factors, the resultant force, the hypotenuse — so nothing here decides anything about
// the maths or the physics. If a value is missing, the component draws less, never something made up.

import { useState } from "react";
import { AtomStructure, ParticleBoxes, PeriodicTable } from "./chemistry";

type Data = Record<string, unknown>;

const num = (data: Data, key: string, fallback = 0): number =>
  typeof data[key] === "number" ? (data[key] as number) : fallback;
const str = (data: Data, key: string): string => (typeof data[key] === "string" ? (data[key] as string) : "");
const list = (data: Data, key: string): Data[] => (Array.isArray(data[key]) ? (data[key] as Data[]) : []);
const power = (f: Data): string => (num(f, "power") > 1 ? `${num(f, "prime")}^${num(f, "power")}` : `${num(f, "prime")}`);
const tidy = (value: number): string => (Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3))));

export function VennFactors({ data }: { data: Data }) {
  const shared = list(data, "shared").map(power).join(" × ") || "1";
  return (
    <svg viewBox="0 0 320 190" className="w-full max-w-md" role="img" aria-label="Prime factors of two numbers">
      <circle cx="120" cy="90" r="70" fill="#FFEDD5" stroke="#FB923C" strokeWidth="2" opacity="0.75" />
      <circle cx="200" cy="90" r="70" fill="#E0E7FF" stroke="#818CF8" strokeWidth="2" opacity="0.75" />
      <text x="70" y="26" textAnchor="middle" className="fill-orange-700 text-[13px] font-bold">
        {num(data, "first")}
      </text>
      <text x="250" y="26" textAnchor="middle" className="fill-indigo-700 text-[13px] font-bold">
        {num(data, "second")}
      </text>
      <text x="80" y="95" textAnchor="middle" className="fill-slate-800 text-[13px]">
        {list(data, "only_first").map(power).join(" × ") || "—"}
      </text>
      <text x="160" y="95" textAnchor="middle" className="fill-slate-900 text-[13px] font-bold">
        {shared}
      </text>
      <text x="240" y="95" textAnchor="middle" className="fill-slate-800 text-[13px]">
        {list(data, "only_second").map(power).join(" × ") || "—"}
      </text>
      <text x="160" y="175" textAnchor="middle" className="fill-slate-600 text-[12px]">
        HCF = {num(data, "hcf")} (the middle) · LCM = {num(data, "lcm")} (everything)
      </text>
    </svg>
  );
}

export function NumberLine({ data }: { data: Data }) {
  const start = num(data, "start");
  const end = num(data, "end", start + 1);
  const span = end - start || 1;
  const x = (value: number) => 20 + ((value - start) / span) * 280;
  const shadeFrom = data.shade_from as number | null;
  const shadeTo = data.shade_to as number | null;
  const values = (Array.isArray(data.values) ? (data.values as number[]) : []).filter((v) => typeof v === "number");
  return (
    <svg viewBox="0 0 320 80" className="w-full max-w-md" role="img" aria-label="Number line">
      {typeof shadeFrom === "number" && typeof shadeTo === "number" && (
        <rect x={x(shadeFrom)} y="30" width={Math.max(1, x(shadeTo) - x(shadeFrom))} height="12" fill="#FDBA74" />
      )}
      <line x1="20" y1="36" x2="300" y2="36" stroke="#334155" strokeWidth="2" />
      {[start, end].map((value) => (
        <g key={`end-${value}`}>
          <line x1={x(value)} y1="28" x2={x(value)} y2="44" stroke="#334155" strokeWidth="2" />
          <text x={x(value)} y="62" textAnchor="middle" className="fill-slate-600 text-[12px]">
            {tidy(value)}
          </text>
        </g>
      ))}
      {values.map((value) => (
        <g key={`v-${value}`}>
          <circle cx={x(value)} cy="36" r="5" fill="#EA580C" />
          <text x={x(value)} y="20" textAnchor="middle" className="fill-orange-700 text-[12px] font-bold">
            {tidy(value)}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function BarModel({ data }: { data: Data }) {
  const parts = list(data, "parts");
  const total = num(data, "total") || parts.reduce((sum, part) => sum + num(part, "value"), 0) || 1;
  let x = 10;
  return (
    <svg viewBox="0 0 320 110" className="w-full max-w-md" role="img" aria-label="Bar model">
      {str(data, "total_label") && (
        <text x="10" y="18" className="fill-slate-700 text-[12px] font-semibold">
          {str(data, "total_label")}
        </text>
      )}
      {parts.map((part, i) => {
        const width = (num(part, "value") / total) * 300;
        const box = (
          <g key={i}>
            <rect
              x={x}
              y="30"
              width={Math.max(2, width)}
              height="34"
              fill={i % 2 ? "#C7D2FE" : "#FED7AA"}
              stroke="#475569"
              strokeWidth="1"
            />
            <text x={x + width / 2} y="52" textAnchor="middle" className="fill-slate-900 text-[12px] font-semibold">
              {tidy(num(part, "value"))}
            </text>
            <text x={x + width / 2} y="80" textAnchor="middle" className="fill-slate-600 text-[11px]">
              {str(part, "label")}
            </text>
          </g>
        );
        x += width;
        return box;
      })}
    </svg>
  );
}

export function RightTriangle({ data }: { data: Data }) {
  const base = num(data, "base", 1);
  const height = num(data, "height", 1);
  const scale = Math.min(230 / base, 120 / height);
  const w = base * scale;
  const h = height * scale;
  const x0 = 45;
  const y0 = 150;
  return (
    <svg viewBox="0 0 320 175" className="w-full max-w-md" role="img" aria-label="Right-angled triangle">
      <polygon
        points={`${x0},${y0} ${x0 + w},${y0} ${x0},${y0 - h}`}
        fill="#DCFCE7"
        stroke="#16A34A"
        strokeWidth="2"
      />
      <rect x={x0} y={y0 - 14} width="14" height="14" fill="none" stroke="#16A34A" strokeWidth="1.5" />
      <text x={x0 + w / 2} y={y0 + 18} textAnchor="middle" className="fill-slate-700 text-[12px]">
        {str(data, "base_label") || tidy(base)}
      </text>
      <text x={x0 - 8} y={y0 - h / 2} textAnchor="end" className="fill-slate-700 text-[12px]">
        {str(data, "height_label") || tidy(height)}
      </text>
      <text x={x0 + w / 2 + 14} y={y0 - h / 2 - 6} className="fill-emerald-800 text-[12px] font-semibold">
        {str(data, "hypotenuse_label") || tidy(num(data, "hypotenuse"))}
      </text>
    </svg>
  );
}

export function ForceArrows({ data }: { data: Data }) {
  const forces = list(data, "forces");
  const unit = str(data, "unit") || "N";
  const biggest = Math.max(1, ...forces.map((f) => num(f, "magnitude")));
  const resultant = (data.resultant as Data) ?? {};
  const cx = 160;
  const cy = 95;
  const reach = (magnitude: number) => 30 + (magnitude / biggest) * 55;
  const ends: Record<string, [number, number]> = {
    left: [-1, 0],
    right: [1, 0],
    up: [0, -1],
    down: [0, 1],
  };
  return (
    <svg viewBox="0 0 320 190" className="w-full max-w-md" role="img" aria-label="Forces on a body">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#0F766E" />
        </marker>
      </defs>
      <rect x={cx - 28} y={cy - 22} width="56" height="44" rx="6" fill="#CCFBF1" stroke="#0F766E" strokeWidth="2" />
      <text x={cx} y={cy + 5} textAnchor="middle" className="fill-teal-900 text-[12px] font-semibold">
        {str(data, "body").slice(0, 10)}
      </text>
      {forces.map((force, i) => {
        const [dx, dy] = ends[str(force, "direction")] ?? [1, 0];
        const length = reach(num(force, "magnitude"));
        const x2 = cx + dx * length;
        const y2 = cy + dy * length;
        return (
          <g key={i}>
            <line
              x1={cx + dx * 30}
              y1={cy + dy * 24}
              x2={x2}
              y2={y2}
              stroke="#0F766E"
              strokeWidth="3"
              markerEnd="url(#arrow)"
            />
            <text
              x={x2 + dx * 8}
              y={y2 + dy * 14 - 6}
              textAnchor={dx === 0 ? "middle" : dx > 0 ? "start" : "end"}
              className="fill-teal-900 text-[11px] font-semibold"
            >
              {str(force, "label")} {tidy(num(force, "magnitude"))} {unit}
            </text>
          </g>
        );
      })}
      <text x={cx} y="182" textAnchor="middle" className="fill-slate-600 text-[12px]">
        Resultant: {tidy(num(resultant, "size"))} {unit}
        {num(resultant, "size") === 0 ? " — the forces are balanced" : ""}
      </text>
    </svg>
  );
}

export function Wave({ data }: { data: Data }) {
  const amplitude = 30;
  const mid = 70;
  const path = Array.from({ length: 121 }, (_, i) => {
    const x = 20 + i * 2.3;
    const y = mid - amplitude * Math.sin((i / 120) * 4 * Math.PI);
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const frequency = data.frequency_hz as number | null;
  const speed = data.speed_ms as number | null;
  return (
    <svg viewBox="0 0 320 150" className="w-full max-w-md" role="img" aria-label="A wave">
      <line x1="20" y1={mid} x2="300" y2={mid} stroke="#CBD5E1" strokeWidth="1" />
      <path d={path} fill="none" stroke="#7C3AED" strokeWidth="2.5" />
      <line x1="20" y1="118" x2="160" y2="118" stroke="#7C3AED" strokeWidth="1.5" strokeDasharray="4 3" />
      <text x="90" y="134" textAnchor="middle" className="fill-violet-700 text-[12px]">
        wavelength {tidy(num(data, "wavelength_m"))} m
      </text>
      <line x1="305" y1={mid - amplitude} x2="305" y2={mid} stroke="#7C3AED" strokeWidth="1.5" strokeDasharray="4 3" />
      <text x="300" y={mid - amplitude - 6} textAnchor="end" className="fill-violet-700 text-[12px]">
        amplitude {tidy(num(data, "amplitude_cm"))} cm
      </text>
      {(frequency || speed) && (
        <text x="20" y="18" className="fill-slate-600 text-[12px]">
          {frequency ? `f = ${tidy(frequency)} Hz` : ""}
          {frequency && speed ? " · " : ""}
          {speed ? `v = ${tidy(speed)} m/s` : ""}
        </text>
      )}
    </svg>
  );
}

// Axes shared by the grid and the straight-line graph: same window, same ticks, so the two look like the same
// textbook. The window and tick spacing were computed by the API.
function Axes({ data, children }: { data: Data; children: React.ReactNode }) {
  const xMin = num(data, "x_min", -10);
  const xMax = num(data, "x_max", 10);
  const yMin = num(data, "y_min", -10);
  const yMax = num(data, "y_max", 10);
  const px = (x: number) => 30 + ((x - xMin) / (xMax - xMin || 1)) * 260;
  const py = (y: number) => 170 - ((y - yMin) / (yMax - yMin || 1)) * 150;
  const xStep = num(data, "x_step", 1);
  const yStep = num(data, "y_step", 1);
  const ticks = (from: number, to: number, step: number) => {
    const first = Math.ceil(from / step) * step;
    const out: number[] = [];
    for (let v = first; v <= to + 1e-9; v += step) out.push(Number(v.toFixed(6)));
    return out;
  };
  const zeroY = yMin <= 0 && yMax >= 0 ? py(0) : py(yMin);
  const zeroX = xMin <= 0 && xMax >= 0 ? px(0) : px(xMin);
  return (
    <svg viewBox="0 0 320 200" className="w-full max-w-md" role="img" aria-label="Graph">
      {ticks(xMin, xMax, xStep).map((v) => (
        <line key={`gx${v}`} x1={px(v)} y1={py(yMin)} x2={px(v)} y2={py(yMax)} stroke="#E2E8F0" strokeWidth="1" />
      ))}
      {ticks(yMin, yMax, yStep).map((v) => (
        <line key={`gy${v}`} x1={px(xMin)} y1={py(v)} x2={px(xMax)} y2={py(v)} stroke="#E2E8F0" strokeWidth="1" />
      ))}
      <line x1={px(xMin)} y1={zeroY} x2={px(xMax)} y2={zeroY} stroke="#334155" strokeWidth="1.5" />
      <line x1={zeroX} y1={py(yMin)} x2={zeroX} y2={py(yMax)} stroke="#334155" strokeWidth="1.5" />
      {ticks(xMin, xMax, xStep)
        .filter((v) => v !== 0)
        .map((v) => (
          <text key={`tx${v}`} x={px(v)} y={zeroY + 13} textAnchor="middle" className="fill-slate-500 text-[9px]">
            {tidy(v)}
          </text>
        ))}
      {ticks(yMin, yMax, yStep)
        .filter((v) => v !== 0)
        .map((v) => (
          <text key={`ty${v}`} x={zeroX - 5} y={py(v) + 3} textAnchor="end" className="fill-slate-500 text-[9px]">
            {tidy(v)}
          </text>
        ))}
      <text x={px(xMax)} y={zeroY - 6} textAnchor="end" className="fill-slate-500 text-[10px]">
        x
      </text>
      <text x={zeroX + 8} y={py(yMax) + 8} className="fill-slate-500 text-[10px]">
        y
      </text>
      {children}
      <Plot px={px} py={py} data={data} />
    </svg>
  );
}

function Plot({ px, py, data }: { px: (x: number) => number; py: (y: number) => number; data: Data }) {
  const points = list(data, "points").map((p) => ({ x: num(p, "x"), y: num(p, "y"), label: str(p, "label") }));
  const ends = list(data, "ends").map((p) => ({ x: num(p, "x"), y: num(p, "y") }));
  const join = data.join === true;
  return (
    <>
      {ends.length === 2 && (
        <line
          x1={px(ends[0].x)}
          y1={py(ends[0].y)}
          x2={px(ends[1].x)}
          y2={py(ends[1].y)}
          stroke="#7C3AED"
          strokeWidth="2.5"
        />
      )}
      {join && points.length > 1 && (
        <polygon
          points={points.map((p) => `${px(p.x)},${py(p.y)}`).join(" ")}
          fill={points.length > 2 ? "#FFEDD5" : "none"}
          stroke="#EA580C"
          strokeWidth="2"
        />
      )}
      {points.map((point, i) => (
        <g key={i}>
          <circle cx={px(point.x)} cy={py(point.y)} r="4" fill="#EA580C" />
          <text x={px(point.x) + 6} y={py(point.y) - 6} className="fill-orange-700 text-[10px] font-semibold">
            {point.label || `(${tidy(point.x)}, ${tidy(point.y)})`}
          </text>
        </g>
      ))}
    </>
  );
}

export function CoordinateGrid({ data }: { data: Data }) {
  return <Axes data={data}>{null}</Axes>;
}

export function StraightLineGraph({ data }: { data: Data }) {
  const origM = num(data, "gradient", 1);
  const origC = num(data, "intercept", 0);
  const [interactive, setInteractive] = useState(false);
  const [m, setM] = useState(origM);
  const [c, setC] = useState(origC);

  const activeM = interactive ? m : origM;
  const activeC = interactive ? c : origC;

  const xMin = num(data, "x_min", -10);
  const xMax = num(data, "x_max", 10);

  // Recompute ends and points dynamically when user slides
  const dynamicData: Data = interactive
    ? {
        ...data,
        ends: [
          { x: xMin, y: activeM * xMin + activeC },
          { x: xMax, y: activeM * xMax + activeC },
        ],
        points: [
          { x: 0, y: activeC, label: `(0, ${tidy(activeC)})` },
          { x: 2, y: activeM * 2 + activeC, label: `(2, ${tidy(activeM * 2 + activeC)})` },
        ],
      }
    : data;

  const sign = activeC >= 0 ? `+ ${tidy(activeC)}` : `- ${tidy(Math.abs(activeC))}`;
  const eqStr = `y = ${tidy(activeM)}x ${sign}`;

  return (
    <div className="flex flex-col gap-2">
      <Axes data={dynamicData}>
        <text x="300" y="16" textAnchor="end" className="fill-violet-700 text-[12px] font-bold">
          {eqStr}
        </text>
        <text x="30" y="16" className="fill-slate-500 text-[10px]">
          gradient {tidy(activeM)} · crosses y at {tidy(activeC)}
        </text>
      </Axes>

      <div className="rounded-xl border border-violet-100 bg-violet-50/50 p-2.5">
        <div className="flex items-center justify-between gap-2 mb-1">
          <button
            onClick={() => setInteractive(!interactive)}
            className="text-[11px] font-fun font-bold text-violet-800 hover:underline"
          >
            {interactive ? "🔒 Lock to lesson values" : "✨ Experiment: change m and c"}
          </button>
          {interactive && (
            <button
              onClick={() => {
                setM(origM);
                setC(origC);
              }}
              className="text-[10px] text-slate-500 hover:text-slate-800"
            >
              Reset
            </button>
          )}
        </div>

        {interactive && (
          <div className="grid grid-cols-2 gap-3 pt-1 text-[11px] text-slate-700">
            <div>
              <div className="flex justify-between">
                <span>Gradient (m):</span>
                <span className="font-bold text-violet-700">{tidy(m)}</span>
              </div>
              <input
                type="range"
                min="-4"
                max="4"
                step="0.5"
                value={m}
                onChange={(e) => setM(Number(e.target.value))}
                className="w-full h-1.5 accent-violet-600 cursor-pointer"
              />
            </div>
            <div>
              <div className="flex justify-between">
                <span>Intercept (c):</span>
                <span className="font-bold text-violet-700">{tidy(c)}</span>
              </div>
              <input
                type="range"
                min="-6"
                max="6"
                step="1"
                value={c}
                onChange={(e) => setC(Number(e.target.value))}
                className="w-full h-1.5 accent-violet-600 cursor-pointer"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function RayDiagram({ data }: { data: Data }) {
  const reflecting = str(data, "behaviour") === "reflection";
  const angleIn = num(data, "angle_in", 30);
  const angleOut = num(data, "angle_out", angleIn);
  const cx = 160;
  const cy = 105;
  const reach = 85;
  const rad = (deg: number) => (deg * Math.PI) / 180;
  // Angles are measured from the normal, as the syllabus does. The incoming ray arrives from the upper left.
  const inX = cx - reach * Math.sin(rad(angleIn));
  const inY = cy - reach * Math.cos(rad(angleIn));
  const outX = cx + reach * Math.sin(rad(angleOut));
  const outY = reflecting ? cy - reach * Math.cos(rad(angleOut)) : cy + reach * Math.cos(rad(angleOut));
  return (
    <svg viewBox="0 0 320 200" className="w-full max-w-md" role="img" aria-label="Ray of light at a surface">
      <defs>
        <marker id="ray" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 z" fill="#B45309" />
        </marker>
      </defs>
      {!reflecting && <rect x="20" y={cy} width="280" height="70" fill="#DBEAFE" stroke="#60A5FA" strokeWidth="1.5" />}
      <line x1="20" y1={cy} x2="300" y2={cy} stroke="#334155" strokeWidth={reflecting ? 3 : 2} />
      {reflecting && (
        <g stroke="#334155" strokeWidth="1">
          {Array.from({ length: 14 }, (_, i) => (
            <line key={i} x1={24 + i * 20} y1={cy + 2} x2={16 + i * 20} y2={cy + 12} />
          ))}
        </g>
      )}
      <line x1={cx} y1={cy - 92} x2={cx} y2={cy + 62} stroke="#94A3B8" strokeWidth="1" strokeDasharray="5 4" />
      <text x={cx + 5} y={cy - 84} className="fill-slate-500 text-[10px]">
        normal
      </text>
      <line x1={inX} y1={inY} x2={cx} y2={cy} stroke="#B45309" strokeWidth="2.5" markerEnd="url(#ray)" />
      <line x1={cx} y1={cy} x2={outX} y2={outY} stroke="#B45309" strokeWidth="2.5" markerEnd="url(#ray)" />
      <text x={cx - 40} y={cy - 18} textAnchor="end" className="fill-amber-800 text-[11px] font-semibold">
        {tidy(angleIn)}°
      </text>
      <text x={cx + 40} y={reflecting ? cy - 18 : cy + 30} className="fill-amber-800 text-[11px] font-semibold">
        {tidy(angleOut)}°
      </text>
      <text x="160" y="190" textAnchor="middle" className="fill-slate-600 text-[11px]">
        {reflecting
          ? `Reflected at the same angle it arrived (${str(data, "surface")})`
          : `Into the ${str(data, "surface")}: n = ${tidy(num(data, "refractive_index"))}, critical angle ${tidy(num(data, "critical_angle"))}°`}
      </text>
    </svg>
  );
}

export function Circuit({ data }: { data: Data }) {
  const parts = list(data, "components");
  const parallel = str(data, "arrangement") === "parallel";
  const left = 40;
  const right = 280;
  const top = 55;
  const bottom = 150;
  const wire = { stroke: "#334155", strokeWidth: 2, fill: "none" } as const;
  const width = 46;
  const slot = (i: number) => left + 40 + i * ((right - left - 60) / Math.max(1, parts.length));
  return (
    <svg viewBox="0 0 320 200" className="w-full max-w-md" role="img" aria-label="Circuit diagram">
      <polyline points={`${left},${top} ${right},${top}`} {...wire} />
      <polyline points={`${left},${bottom} ${right},${bottom}`} {...wire} />
      <polyline points={`${left},${top} ${left},${bottom}`} {...wire} />
      <polyline points={`${right},${top} ${right},${bottom}`} {...wire} />
      {/* the cell, on the bottom wire */}
      <line x1={155} y1={bottom - 11} x2={155} y2={bottom + 11} stroke="#334155" strokeWidth="2.5" />
      <line x1={165} y1={bottom - 6} x2={165} y2={bottom + 6} stroke="#334155" strokeWidth="5" />
      <text x={160} y={bottom + 26} textAnchor="middle" className="fill-slate-700 text-[11px] font-semibold">
        {tidy(num(data, "emf_v"))} V
      </text>
      {parts.map((part, i) => {
        const x = parallel ? 150 : slot(i);
        const y = parallel ? top + 18 + i * 26 : top;
        return (
          <g key={i}>
            {parallel && (
              <>
                <polyline points={`${left + 60},${top} ${left + 60},${y} ${x - width / 2},${y}`} {...wire} />
                <polyline points={`${x + width / 2},${y} ${right - 60},${y} ${right - 60},${top}`} {...wire} />
              </>
            )}
            <rect x={x - width / 2} y={y - 11} width={width} height="22" fill="#FFF7ED" stroke="#334155" strokeWidth="2" />
            <text x={x} y={y + 4} textAnchor="middle" className="fill-slate-900 text-[10px] font-semibold">
              {tidy(num(part, "resistance_ohm"))} Ω
            </text>
            <text x={x} y={y - 16} textAnchor="middle" className="fill-slate-600 text-[10px]">
              {str(part, "label")}
            </text>
          </g>
        );
      })}
      <text x="160" y="192" textAnchor="middle" className="fill-slate-600 text-[11px]">
        {parallel ? "In parallel" : "In series"}: total {tidy(num(data, "total_resistance_ohm"))} Ω · current{" "}
        {tidy(num(data, "current_a"))} A
      </text>
    </svg>
  );
}

export const DIAGRAMS: Record<string, (props: { data: Data }) => React.ReactElement> = {
  venn_factors: VennFactors,
  number_line: NumberLine,
  bar_model: BarModel,
  right_triangle: RightTriangle,
  force_arrows: ForceArrows,
  wave: Wave,
  coordinate_grid: CoordinateGrid,
  straight_line_graph: StraightLineGraph,
  ray_diagram: RayDiagram,
  circuit: Circuit,
  atom_structure: AtomStructure,
  particle_boxes: ParticleBoxes,
  periodic_table: PeriodicTable,
};
