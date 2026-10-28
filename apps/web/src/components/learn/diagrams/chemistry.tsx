// Chemistry pictures (lesson v5). Each draws exactly what the API computed from its element table — the protons,
// neutrons and electron shells, a box's classification, the Periodic Table's layout — and decides nothing itself.

type Data = Record<string, unknown>;

const num = (data: Data, key: string): number => (typeof data[key] === "number" ? (data[key] as number) : 0);
const str = (data: Data, key: string): string => (typeof data[key] === "string" ? (data[key] as string) : "");
const nums = (data: Data, key: string): number[] =>
  Array.isArray(data[key]) ? (data[key] as unknown[]).filter((x): x is number => typeof x === "number") : [];
const list = (data: Data, key: string): Data[] => (Array.isArray(data[key]) ? (data[key] as Data[]) : []);

const PROTON = "#EF4444";
const NEUTRON = "#94A3B8";
const ELECTRON = "#2563EB";

// Points spread evenly in a disc (a sunflower pattern), so any number of particles packs into a round nucleus.
function packed(count: number, radius: number): [number, number][] {
  const golden = Math.PI * (3 - Math.sqrt(5));
  return Array.from({ length: count }, (_, i) => {
    const r = radius * Math.sqrt((i + 0.5) / count);
    return [r * Math.cos(i * golden), r * Math.sin(i * golden)];
  });
}

export function AtomStructure({ data }: { data: Data }) {
  const protons = num(data, "protons");
  const neutrons = num(data, "neutrons");
  const charge = num(data, "charge");
  const shells = nums(data, "shells");
  const symbol = str(data, "symbol");
  const cx = 150;
  const cy = 160;
  const particle = 5.5;
  const total = protons + neutrons;
  const nucleusR = Math.max(12, Math.sqrt(total) * particle * 1.05);
  // Protons and neutrons alternate through the cluster so both are visible, as in the book's drawings.
  const order = Array.from({ length: total }, (_, i) => (i % 2 === 0 ? i / 2 < protons : (i - 1) / 2 >= neutrons));
  const positions = packed(total, Math.max(0, nucleusR - particle));
  const radii = shells.map((_, i) => nucleusR + 22 + i * 28);
  const chargeText = charge === 0 ? "" : `${Math.abs(charge) > 1 ? Math.abs(charge) : ""}${charge > 0 ? "+" : "−"}`;
  return (
    <svg viewBox="0 0 440 320" className="w-full max-w-xl" role="img" aria-label={`Structure of ${str(data, "name")}`}>
      {radii.map((r, i) => (
        <circle key={`s${i}`} cx={cx} cy={cy} r={r} fill="none" stroke="#CBD5E1" strokeWidth="1.5" strokeDasharray="4 3" />
      ))}
      {shells.map((count, i) =>
        Array.from({ length: count }, (_, j) => {
          const angle = (2 * Math.PI * j) / count - Math.PI / 2 + i * 0.4;
          const x = cx + radii[i] * Math.cos(angle);
          const y = cy + radii[i] * Math.sin(angle);
          return (
            <g key={`e${i}-${j}`}>
              <circle cx={x} cy={y} r="6" fill={ELECTRON} />
              <text x={x} y={y + 3.5} textAnchor="middle" className="fill-white text-[10px] font-bold">
                −
              </text>
            </g>
          );
        }),
      )}
      <circle cx={cx} cy={cy} r={nucleusR + 3} fill="#FEF2F2" stroke="#FCA5A5" strokeWidth="1" />
      {positions.map(([x, y], i) => (
        <g key={`n${i}`}>
          <circle cx={cx + x} cy={cy + y} r={particle} fill={order[i] ? PROTON : NEUTRON} stroke="white" strokeWidth="0.8" />
          {order[i] && (
            <text x={cx + x} y={cy + y + 3} textAnchor="middle" className="fill-white text-[8px] font-bold">
              +
            </text>
          )}
        </g>
      ))}

      {/* Labels with leader lines */}
      <line x1={cx + nucleusR * 0.7} y1={cy - nucleusR * 0.7} x2="300" y2="40" stroke="#64748B" strokeWidth="1" />
      <text x="304" y="44" className="fill-slate-700 text-[12px] font-semibold">
        nucleus ({protons} p, {neutrons} n)
      </text>
      {radii.length > 0 && (
        <>
          <line x1={cx + radii[radii.length - 1]} y1={cy} x2="300" y2={cy} stroke="#64748B" strokeWidth="1" />
          <text x="304" y={cy + 4} className="fill-slate-700 text-[12px] font-semibold">
            electron shells
          </text>
          <text x="304" y={cy + 20} className="fill-slate-500 text-[11px]">
            {shells.join(", ")}
          </text>
        </>
      )}

      {/* Nuclide notation: mass number over proton number */}
      <text x="12" y="30" className="fill-slate-600 text-[12px]">
        {num(data, "mass_number")}
      </text>
      <text x="12" y="48" className="fill-slate-600 text-[12px]">
        {protons}
      </text>
      <text x="34" y="46" className="fill-slate-900 text-[24px] font-bold">
        {symbol}
      </text>
      {chargeText && (
        <text x={34 + symbol.length * 15} y="28" className="fill-slate-900 text-[13px] font-bold">
          {chargeText}
        </text>
      )}

      {/* Legend */}
      {[
        [PROTON, "proton", "charge +1, mass 1"],
        [NEUTRON, "neutron", "charge 0, mass 1"],
        [ELECTRON, "electron", "charge −1, mass negligible"],
      ].map(([colour, name, facts], i) => (
        <g key={name}>
          <circle cx="306" cy={232 + i * 24} r="6" fill={colour} />
          <text x="318" y={236 + i * 24} className="fill-slate-800 text-[11px] font-semibold">
            {name}
          </text>
          <text x="318" y={248 + i * 24} className="fill-slate-500 text-[9.5px]">
            {facts}
          </text>
        </g>
      ))}
    </svg>
  );
}

// Colours by element, CPK-like, so O is red and C dark grey in every box of every lesson.
const ATOM_COLOURS: Record<string, string> = {
  H: "#F8FAFC",
  C: "#334155",
  N: "#3B82F6",
  O: "#EF4444",
  Cl: "#22C55E",
  F: "#86EFAC",
  Br: "#9A3412",
  S: "#EAB308",
  P: "#F97316",
  Na: "#A855F7",
  K: "#7C3AED",
  Mg: "#15803D",
  Ca: "#6B7280",
  Fe: "#B45309",
  Cu: "#C2410C",
  He: "#F9A8D4",
  Ne: "#F472B6",
  Ar: "#EC4899",
};
const colour = (s: string) => ATOM_COLOURS[s] ?? "#A1A1AA";

export function ParticleBoxes({ data }: { data: Data }) {
  const boxes = list(data, "boxes");
  const size = 150;
  const gap = 20;
  const width = boxes.length * size + (boxes.length - 1) * gap;
  const symbols = Array.from(
    new Set(boxes.flatMap((b) => list(b, "particles").flatMap((p) => (Array.isArray(p.atoms) ? (p.atoms as string[]) : [])))),
  );
  return (
    <svg viewBox={`0 0 ${width} ${size + 90}`} className="w-full max-w-2xl" role="img" aria-label="Boxes of particles">
      {boxes.map((box, b) => {
        const x0 = b * (size + gap);
        const particles = list(box, "particles").flatMap((p) =>
          Array.from({ length: num(p, "count") }, () => (Array.isArray(p.atoms) ? (p.atoms as string[]) : [])),
        );
        const columns = Math.ceil(Math.sqrt(particles.length));
        const cell = (size - 20) / Math.max(columns, 1);
        return (
          <g key={b}>
            <rect x={x0} y="4" width={size} height={size} rx="10" fill="white" stroke="#94A3B8" strokeWidth="1.5" />
            {particles.map((atoms, i) => {
              const col = i % columns;
              const row = Math.floor(i / columns);
              // A little fixed wobble so the particles look scattered, the same on every visit.
              const wobble = ((i * 37) % 11) - 5;
              const px = x0 + 10 + col * cell + cell / 2 + wobble;
              const py = 14 + row * cell + cell / 2 - wobble / 2;
              const r = Math.min(9, cell / (atoms.length + 1.2));
              return (
                <g key={i}>
                  {atoms.map((s, k) => {
                    const ax = px + (k - (atoms.length - 1) / 2) * r * 1.6;
                    return <circle key={k} cx={ax} cy={py} r={r} fill={colour(s)} stroke="#334155" strokeWidth="0.8" />;
                  })}
                </g>
              );
            })}
            <text x={x0 + size / 2} y={size + 24} textAnchor="middle" className="fill-slate-900 text-[12px] font-bold">
              {str(box, "label")}
            </text>
            <text x={x0 + size / 2} y={size + 40} textAnchor="middle" className="fill-slate-500 text-[11px]">
              {list(box, "particles").map((p) => str(p, "formula")).join(" + ")}
            </text>
          </g>
        );
      })}
      {symbols.map((s, i) => (
        <g key={s}>
          <circle cx={10 + i * 56} cy={size + 66} r="7" fill={colour(s)} stroke="#334155" strokeWidth="0.8" />
          <text x={22 + i * 56} y={size + 70} className="fill-slate-700 text-[11px]">
            {s} atom
          </text>
        </g>
      ))}
    </svg>
  );
}

const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII"];

export function PeriodicTable({ data }: { data: Data }) {
  const cells = list(data, "cells");
  const groups = new Set(nums(data, "highlight_groups"));
  const lit = new Set(Array.isArray(data.highlight_elements) ? (data.highlight_elements as string[]) : []);
  const w = 30;
  const h = 34;
  const left = 26;
  const top = 26;
  // 18 columns: Groups I and II, ten transition columns, then Groups III to VIII.
  const column = (c: Data): number => {
    const group = typeof c.group === "number" ? (c.group as number) : null;
    const z = num(c, "z");
    if (z === 1) return 1;
    if (group === null) return 3 + (z - 21);
    return group <= 2 ? group : group + 10;
  };
  return (
    <svg viewBox={`0 0 ${left + 18 * w + 8} ${top + 4 * h + 30}`} className="w-full max-w-3xl" role="img" aria-label="The Periodic Table">
      {[1, 2, 3, 4, 5, 6, 7, 8].map((g) => {
        const col = g <= 2 ? g : g + 10;
        return (
          <text key={g} x={left + (col - 0.5) * w} y={top - 8} textAnchor="middle" className={`text-[10px] font-bold ${groups.has(g) ? "fill-orange-700" : "fill-slate-500"}`}>
            {ROMAN[g]}
          </text>
        );
      })}
      {[1, 2, 3, 4].map((p) => (
        <text key={p} x="10" y={top + (p - 0.5) * h + 4} textAnchor="middle" className="fill-slate-500 text-[10px] font-bold">
          {p}
        </text>
      ))}
      {cells.map((c) => {
        const col = column(c);
        const period = num(c, "period");
        const x = left + (col - 1) * w;
        const y = top + (period - 1) * h;
        const symbol = str(c, "symbol");
        const on = lit.has(symbol) || (typeof c.group === "number" && groups.has(c.group as number));
        const transition = c.group === null && num(c, "z") !== 1;
        return (
          <g key={symbol}>
            <rect
              x={x + 1}
              y={y + 1}
              width={w - 2}
              height={h - 2}
              rx="3"
              fill={on ? "#FED7AA" : transition ? "#F1F5F9" : "white"}
              stroke={on ? "#EA580C" : "#CBD5E1"}
              strokeWidth={on ? 1.5 : 1}
            />
            <text x={x + 4} y={y + 10} className="fill-slate-500 text-[7px]">
              {num(c, "z")}
            </text>
            <text x={x + w / 2} y={y + 24} textAnchor="middle" className="fill-slate-900 text-[11px] font-bold">
              {symbol}
            </text>
          </g>
        );
      })}
      <text x={left + 7.5 * w} y={top + 4 * h + 16} textAnchor="middle" className="fill-slate-500 text-[9px]">
        transition elements
      </text>
      <text x={left} y={top + 4 * h + 16} className="fill-slate-500 text-[9px]">
        group numbers along the top, periods down the side
      </text>
    </svg>
  );
}
