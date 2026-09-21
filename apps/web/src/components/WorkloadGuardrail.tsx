import { minutes } from "@/lib/format";

export function WorkloadGuardrail({
  dailyMinutes = 45,
  iitSchedule = "Mon, Thu, Sat (6h/week)",
  sleepCutoff = "Strict cutoff at 9:30 PM ✓",
  status = "Optimal Rest",
}: {
  dailyMinutes?: number;
  iitSchedule?: string;
  sleepCutoff?: string;
  status?: string;
}) {
  return (
    <div className="bg-white rounded-3xl border-2 border-slate-200 p-6 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="font-fun font-bold text-slate-900 text-base flex items-center gap-2">
          <span>⚖️</span>
          <span>Workload Balance Guardrail</span>
        </h4>
        <span className="text-xs font-fun font-bold text-orange-600 bg-orange-50 border border-orange-200 px-3 py-1 rounded-full">
          {status}
        </span>
      </div>
      <p className="text-xs text-slate-500 font-medium">
        Balancing IGCSE Cambridge schoolwork with external IIT Foundation classes:
      </p>

      <div className="space-y-2 text-xs pt-1">
        <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
          <span className="text-slate-600 font-medium">Scholr Daily Practice</span>
          <span className="font-fun font-bold text-slate-900">{minutes(dailyMinutes)} / day</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-2xl bg-blue-50/60 border border-blue-100">
          <span className="text-slate-600 font-medium">IIT Foundation ({iitSchedule})</span>
          <span className="font-fun font-bold text-blue-700">Protected schedule</span>
        </div>
        <div className="flex items-center justify-between p-3 rounded-2xl bg-emerald-50 border border-emerald-100">
          <span className="text-emerald-800 font-bold">Sleep & Recovery</span>
          <span className="font-fun font-bold text-emerald-700">{sleepCutoff}</span>
        </div>
      </div>
    </div>
  );
}
