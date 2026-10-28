"use client";

import { useCallback, useEffect, useState } from "react";
import { approveAccount, pendingAccounts, rejectAccount, streamChoices, type PendingAccount, type StreamChoice } from "@/lib/auth";
import { Button, Empty, ErrorNote } from "@/components/ui";

// Who may use Scholr (docs/STUDENT-APP.md D7). Approving grants the streams chosen here and enrolls a student in
// every subject of each one; rejecting is final.
export default function Registrations() {
  const [pending, setPending] = useState<PendingAccount[] | null>(null);
  const [streams, setStreams] = useState<StreamChoice[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    pendingAccounts().then(setPending).catch(setError);
  }, []);

  useEffect(() => {
    load();
    streamChoices().then(setStreams).catch(() => setStreams([]));
  }, [load]);

  if (error) return <main className="mx-auto max-w-3xl p-6"><ErrorNote error={error} /></main>;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <header>
        <h1 className="font-fun text-2xl font-extrabold text-ink">Access requests</h1>
        <p className="text-xs text-muted">Each account can do nothing until it is approved here.</p>
      </header>

      {pending === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : pending.length === 0 ? (
        <Empty>No requests waiting.</Empty>
      ) : (
        pending.map((account) => (
          <RequestCard
            key={account.user_id}
            account={account}
            streams={streams}
            busy={busy === account.user_id}
            onDecide={async (decide) => {
              setBusy(account.user_id);
              try {
                await decide();
                load();
              } catch (err) {
                setError(err);
              } finally {
                setBusy("");
              }
            }}
          />
        ))
      )}
    </main>
  );
}

function RequestCard({
  account,
  streams,
  busy,
  onDecide,
}: {
  account: PendingAccount;
  streams: StreamChoice[];
  busy: boolean;
  onDecide: (decide: () => Promise<unknown>) => void;
}) {
  const [role, setRole] = useState("student");
  const [granted, setGranted] = useState<string[]>(account.requested_streams);
  const [yearGroup, setYearGroup] = useState("");

  return (
    <section className="flex flex-col gap-3 rounded-3xl border-2 border-slate-200/90 bg-white p-5 shadow-sm">
      <div>
        <h2 className="font-semibold text-slate-900">{account.display_name}</h2>
        <p className="text-xs text-muted">
          {account.email} · asked on {new Date(account.requested_at).toLocaleDateString()}
        </p>
        {account.note && <p className="mt-2 text-sm text-slate-700">“{account.note}”</p>}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2 font-semibold text-slate-700">
          Role
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="h-9 rounded-xl border-2 border-slate-200 px-2 text-sm font-normal"
          >
            <option value="student">Student</option>
            <option value="guardian">Parent</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        {role === "student" && (
          <label className="flex items-center gap-2 font-semibold text-slate-700">
            Year group
            <input
              value={yearGroup}
              onChange={(e) => setYearGroup(e.target.value)}
              placeholder="Year 10"
              className="h-9 w-28 rounded-xl border-2 border-slate-200 px-2 text-sm font-normal"
            />
          </label>
        )}
      </div>

      <div className="flex flex-wrap gap-3 text-sm text-slate-700">
        {streams.map((stream) => (
          <label key={stream.key} className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={granted.includes(stream.key)}
              onChange={() =>
                setGranted((current) =>
                  current.includes(stream.key) ? current.filter((k) => k !== stream.key) : [...current, stream.key],
                )
              }
            />
            {stream.name}
          </label>
        ))}
      </div>

      <div className="flex gap-2">
        <Button
          disabled={busy}
          onClick={() => onDecide(() => approveAccount(account.user_id, { role, streams: granted, year_group: yearGroup }))}
        >
          {busy ? "Working…" : "Approve"}
        </Button>
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => onDecide(() => rejectAccount(account.user_id, ""))}
        >
          Reject
        </Button>
      </div>
    </section>
  );
}
