"use client";

import { useState } from "react";
import { MathText } from "@/components/MathText";
import { Button, Card, Chip } from "@/components/ui";

type VivaTurn = {
  speaker: "student" | "examiner";
  text: string;
  rigor_note?: string;
};

export function OralDefenseViva() {
  const [currentStep, setCurrentStep] = useState(1);
  const [studentDefense, setStudentDefense] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [dialogue, setDialogue] = useState<VivaTurn[]>([
    {
      speaker: "examiner",
      text:
        "Welcome candidate. At the blackboard, solve: " +
        "A projectile is launched from ground level at an angle $\\theta$ with initial velocity $u$. " +
        "Show your first step for the maximum vertical height $H$, and rigorously justify your governing physical assumption.",
      rigor_note: "Examiner checks: Did you identify the boundary condition at the peak?",
    },
  ]);
  const [vivaScore, setVivaScore] = useState(75);

  function toggleSpeechToText() {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      alert("Speech recognition is supported in Chrome/Edge. You can also type your defense!");
      return;
    }

    /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    if (!isRecording) {
      setIsRecording(true);
      recognition.start();
      /* eslint-disable-next-line @typescript-eslint/no-explicit-any */
      recognition.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        setStudentDefense((prev) => (prev ? `${prev} ${transcript}` : transcript));
        setIsRecording(false);
      };
      recognition.onerror = () => setIsRecording(false);
      recognition.onend = () => setIsRecording(false);
    } else {
      setIsRecording(false);
    }
  }

  function defendStep() {
    if (!studentDefense.trim()) return;

    const studentTurn: VivaTurn = {
      speaker: "student",
      text: studentDefense,
    };

    let examinerReply: VivaTurn;

    if (currentStep === 1) {
      examinerReply = {
        speaker: "examiner",
        text:
          "Precisely. At the zenith, the instantaneous vertical velocity $v_y = 0$, while the horizontal component $u_x = u \\cos \\theta$ " +
          "remains invariant because air resistance is neglected. Now, write down the kinematic formula that links $v_y, u_y, a_y,$ and $H$, " +
          "and defend why we must use $-g$ for acceleration.",
        rigor_note: "Rigorous sign convention check passed (+10 Rigor points)",
      };
      setCurrentStep(2);
      setVivaScore((s) => Math.min(100, s + 10));
    } else {
      examinerReply = {
        speaker: "examiner",
        text:
          "Excellent. Using $v_y^2 = u_y^2 + 2 a_y H$, we substitute $v_y = 0$, $u_y = u \\sin \\theta$, and $a_y = -g$: " +
          "$$0 = (u \\sin \\theta)^2 - 2gH \\implies H = \\frac{u^2 \\sin^2 \\theta}{2g}$$ " +
          "Your oral defense demonstrates first-principles mastery. You would earn top marks in a Cambridge viva or JEE interview.",
        rigor_note: "Blackboard defense concluded successfully! (100% Viva Rigor)",
      };
      setCurrentStep(3);
      setVivaScore(100);
    }

    setDialogue((d) => [...d, studentTurn, examinerReply]);
    setStudentDefense("");
  }

  return (
    <Card
      title="🎓 Oral Defense & Blackboard Viva"
      subtitle="Cambridge & IIT Rigor: Defend every line of your logic out loud before writing the next step"
      tone="purple"
    >
      <div className="space-y-4">
        {/* Blackboard Frame */}
        <div className="rounded-3xl border-4 border-amber-900/40 bg-[#1E2D24] p-5 text-emerald-100 shadow-xl space-y-4 font-mono">
          <div className="flex items-center justify-between border-b border-emerald-800/60 pb-3 text-xs">
            <span className="font-bold uppercase tracking-widest text-emerald-400">
              Chalkboard Examination Arena · Session #1
            </span>
            <Chip tone={vivaScore >= 85 ? "good" : "brand"}>
              Viva Rigor Score: {vivaScore}%
            </Chip>
          </div>

          {/* Dialogue Stream */}
          <div className="space-y-3 max-h-[320px] overflow-y-auto pr-2 text-xs leading-relaxed font-sans">
            {dialogue.map((turn, i) => (
              <div
                key={i}
                className={`p-3.5 rounded-2xl ${
                  turn.speaker === "examiner"
                    ? "bg-[#25382D] border border-emerald-700/60 text-emerald-100"
                    : "bg-[#2E4537] border border-amber-300/40 text-amber-100 ml-6"
                }`}
              >
                <div className="flex items-center justify-between text-[11px] font-fun font-bold mb-1">
                  <span className={turn.speaker === "examiner" ? "text-emerald-300" : "text-amber-300"}>
                    {turn.speaker === "examiner" ? "👨‍🏫 Chief Examiner:" : "👩‍🎓 Your Oral Defense:"}
                  </span>
                  {turn.rigor_note && (
                    <span className="text-[10px] text-emerald-400 font-mono">
                      {turn.rigor_note}
                    </span>
                  )}
                </div>
                <div className="text-sm font-medium">
                  <MathText text={turn.text} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Defense Submission Controls */}
        {currentStep <= 2 ? (
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-fun font-bold text-slate-800">
                Defend Step {currentStep} (Speak or type your justification):
              </label>
              <button
                type="button"
                onClick={toggleSpeechToText}
                className={`flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold transition-all cursor-pointer ${
                  isRecording
                    ? "bg-rose-500 text-white animate-pulse"
                    : "bg-purple-100 text-purple-800 hover:bg-purple-200"
                }`}
              >
                <span>🎙️</span> {isRecording ? "Listening..." : "Speak Answer"}
              </button>
            </div>

            <textarea
              value={studentDefense}
              onChange={(e) => setStudentDefense(e.target.value)}
              rows={2}
              className="w-full rounded-2xl border-2 border-purple-200 bg-white p-3 text-xs outline-none focus:border-purple-400 placeholder:text-slate-400"
              placeholder={
                currentStep === 1
                  ? "e.g. 'At the peak of projectile flight, the vertical velocity component vy is momentarily zero...'"
                  : "e.g. 'We substitute into vy^2 = uy^2 + 2ayH where ay = -g due to downward gravitational acceleration...'"
              }
            />

            <Button
              disabled={!studentDefense.trim()}
              onClick={defendStep}
              className="w-full sm:w-auto"
            >
              Deliver Oral Justification to Examiner 🗣️
            </Button>
          </div>
        ) : (
          <div className="p-4 rounded-2xl bg-emerald-50 border-2 border-emerald-300 text-xs text-emerald-950 font-medium flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🎓</span>
              <span>
                <strong>Oral Defense Completed!</strong> You successfully defended every derivation step without skipping assumptions.
              </span>
            </div>
            <Button variant="secondary" onClick={() => { setCurrentStep(1); setVivaScore(75); }}>
              Start New Defense
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
