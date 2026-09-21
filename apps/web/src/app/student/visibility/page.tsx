"use client";

import { useMe } from "@/components/AppShell";
import { Card, Chip, Empty } from "@/components/ui";
import { SCOPE_LABELS } from "@/lib/format";

// AC-S6: the student sees exactly what each linked guardian can see.
export default function Visibility() {
  const me = useMe();
  const guardians = me?.guardian_visibility ?? [];
  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="rounded-3xl border-2 border-amber-200 bg-gradient-to-br from-amber-50 via-[#FFF4E8] to-orange-50 p-6 md:p-8 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="h-14 w-14 rounded-3xl bg-amber-100 border border-amber-300 flex items-center justify-center text-3xl shadow-sm select-none">
            👁️
          </div>
          <div>
            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-orange-100 text-orange-800 text-[11px] font-fun font-bold border border-orange-200 mb-1">
              Complete Transparency
            </span>
            <h1 className="text-xl md:text-2xl font-fun font-bold text-slate-900">
              What My Family Can See
            </h1>
            <p className="text-xs text-slate-500 font-medium">
              You always see exactly what your parent or guardian has permission to see.
            </p>
          </div>
        </div>
      </div>

      <Card
        title="Linked Parent Accounts"
        subtitle="Every time a parent opens study chats or learning notes, it is audit-logged for your privacy"
      >
        {guardians.length === 0 && <Empty>No parent account is linked right now.</Empty>}
        <div className="space-y-3 pt-1">
          {guardians.map((g) => (
            <div
              key={g.guardian_name}
              className="flex flex-col gap-2 rounded-2xl border-2 border-amber-200/70 bg-[#FFFDF9] p-4 shadow-2xs"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm font-fun font-bold text-slate-900 flex items-center gap-2">
                  <span>👨‍👩‍👧</span>
                  <span>{g.guardian_name}</span>
                </div>
                <span className="text-[11px] text-slate-400 font-medium">Active Guardian Scope</span>
              </div>
              <div className="flex flex-wrap gap-2 pt-1">
                {g.scopes.map((s) => (
                  <Chip key={s} tone="brand">
                    {SCOPE_LABELS[s] ?? s}
                  </Chip>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl bg-amber-50 border border-amber-200 p-4 text-xs leading-relaxed text-amber-900 space-y-1 mt-2">
          <span className="font-fun font-bold text-orange-800 flex items-center gap-1.5 text-sm">
            <span>🛡️</span> Safety Guardrail Promise
          </span>
          <p>
            If you ever write something that sounds like you might be distressed or unsafe, the app offers immediate guidance and notifies your parent. That is to protect and care for you, never to spy or micromanage your learning.
          </p>
        </div>
      </Card>
    </div>
  );
}
