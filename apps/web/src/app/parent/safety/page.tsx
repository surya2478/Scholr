"use client";

import { useState } from "react";
import { Button, Card, Chip, Empty, ErrorNote } from "@/components/ui";
import { api, type Incident } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useApi } from "@/lib/useApi";
import { useLinkedStudent } from "@/lib/useStudent";

const SEVERITY: Record<number, { tone: "alert" | "warn" | "neutral"; label: string }> = {
  3: { tone: "alert", label: "High" },
  2: { tone: "warn", label: "Medium" },
  1: { tone: "neutral", label: "Low" },
};

function IncidentRow({ incident, onChange }: { incident: Incident; onChange: () => void }) {
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const severity = SEVERITY[incident.severity] ?? SEVERITY[1];

  async function update(status: "acknowledged" | "resolved") {
    setBusy(true);
    setError(null);
    try {
      await api(`/safety/incidents/${incident.id}`, { method: "PATCH", json: { escalation_status: status, notes: notes || null } });
      onChange();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const isResolved = incident.escalation_status === "resolved";

  return (
    <li className={`flex flex-col gap-3 rounded-2xl border p-4.5 transition shadow-xs ${
      isResolved ? "border-line-soft bg-white/60 opacity-80" : "border-slate-200 bg-gradient-to-r from-[#FFFDF9] to-[#FFF9F2]"
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <div className="flex items-center gap-2">
          <Chip tone={severity.tone}>{severity.label} Priority</Chip>
          <span className="font-bold text-ink text-base capitalize">{incident.category.replaceAll("_", " ")}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>🕒 {dateTime(incident.occurred_at)}</span>
          <span className={`rounded-full px-2.5 py-0.5 font-bold uppercase tracking-wider text-[10px] ${
            isResolved ? "bg-emerald-50 text-emerald-700" : "bg-amber-100 text-amber-800"
          }`}>
            {incident.escalation_status}
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-line-soft bg-white/90 p-3 text-xs text-ink-2">
        <span className="font-bold text-ink">Automated response:</span> {incident.action_taken.replaceAll("_", " ")}
      </div>

      {!isResolved && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <input
            value={notes}
            maxLength={2000}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add parental resolution notes (optional)..."
            className="h-10 min-w-[240px] flex-1 rounded-xl border border-line bg-white px-3 text-xs font-medium text-ink focus:border-brand focus:outline-none"
          />
          <Button variant="secondary" disabled={busy} onClick={() => update("acknowledged")}>
            Acknowledge
          </Button>
          <Button disabled={busy} onClick={() => update("resolved")}>
            Mark Resolved ✓
          </Button>
        </div>
      )}
      {error ? <ErrorNote error={error} /> : null}
    </li>
  );
}

export default function Safety() {
  const { id, query, has } = useLinkedStudent();
  const incidents = useApi<Incident[]>(id && has("safety") ? `/safety/incidents?${query}` : null);
  return (
    <div className="flex flex-col gap-6">
      {/* Friendly guardian banner */}
      <section className="relative overflow-hidden rounded-3xl border border-blue-100 bg-gradient-to-r from-[#EFF6FF] via-[#F5F9FF] to-[#FAF5FF] p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1 text-xs font-bold text-blue-800 shadow-xs">
              <span>🛡️</span> Guardian Safeguards
            </div>
            <h1 className="mt-2 text-2xl font-fun font-extrabold tracking-tight text-ink">
              Safety & Wellbeing Alerts
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-2">
              Scholr actively protects student wellbeing. If study interactions suggest distress or safety concerns, support is offered immediately and flagged here. Note: raw chat text is never exposed here to respect trust.
            </p>
          </div>
          <div className="flex items-center gap-3 rounded-2xl border border-blue-200/60 bg-white/90 p-4 shadow-xs">
            <div className="text-3xl">🔒</div>
            <div>
              <div className="text-xs font-bold text-muted uppercase tracking-wider">Privacy Promise</div>
              <div className="font-fun text-sm font-bold text-ink">Child Trust Protected</div>
              <div className="text-[11px] text-muted">Audited parental escalation</div>
            </div>
          </div>
        </div>
      </section>

      <Card
        title="Active & Past Alerts"
        subtitle="Opening this page is logged in the transparency audit trail to maintain reciprocal trust."
      >
        {!has("safety") && <Empty>Your account does not have access to safety alerts.</Empty>}
        {incidents.error ? <ErrorNote error={incidents.error} /> : null}
        {incidents.data?.length === 0 && (
          <div className="rounded-2xl border border-emerald-150 bg-gradient-to-b from-[#F0FDF4] to-[#DCFCE7]/30 p-6 text-center">
            <div className="text-4xl mb-2">✨</div>
            <h3 className="font-fun font-bold text-base text-emerald-900">All Clear & Safe</h3>
            <p className="text-xs text-emerald-700 mt-1 max-w-md mx-auto">
              No safety or distress alerts have been detected. Scholr continues to guard her study sessions quietly in the background.
            </p>
          </div>
        )}
        <ul className="flex flex-col gap-3">
          {incidents.data?.map((i) => <IncidentRow key={i.id} incident={i} onChange={() => void incidents.reload()} />)}
        </ul>
      </Card>
    </div>
  );
}
