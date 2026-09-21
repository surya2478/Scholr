// Official Cambridge IGCSE command words and examiner expectations.

export type CommandWordInfo = {
  meaning: string;
  examinerTip: string;
};

export const COMMAND_WORDS: Record<string, CommandWordInfo> = {
  "calculate": {
    meaning: "Work out from given facts, figures or information.",
    examinerTip: "Always show your working step-by-step. Method (M) marks are awarded even if your final answer has an arithmetic slip.",
  },
  "show that": {
    meaning: "Provide every single step leading to the given result.",
    examinerTip: "Never skip steps or assume the result. You must write out the initial equation, substitution, and rearrangement clearly.",
  },
  "hence": {
    meaning: "You must use your result from the previous part.",
    examinerTip: "Do not restart the calculation from scratch! Examiners demand that you apply your earlier answer directly.",
  },
  "hence or otherwise": {
    meaning: "It is recommended to use your previous answer, but alternative methods are accepted.",
    examinerTip: "Using your previous result is almost always faster and less prone to mistakes.",
  },
  "state": {
    meaning: "Give a specific name, value or brief answer without working.",
    examinerTip: "No calculation is expected. Keep it direct and concise.",
  },
  "describe": {
    meaning: "State the points of a topic or give characteristics and main features.",
    examinerTip: "For graphs/transformations: state all required parameters (e.g. scale factor + centre for enlargement; angle + direction + centre for rotation).",
  },
  "explain": {
    meaning: "Set out reasons or make relationships clear (the why and how).",
    examinerTip: "Use precise syllabus terminology rather than vague everyday words.",
  },
  "solve": {
    meaning: "Find the values that satisfy the equation or inequality.",
    examinerTip: "Show every rearrangement step. If quadratic, remember to check for two solutions.",
  },
  "factorise": {
    meaning: "Write the expression as a product of its factors.",
    examinerTip: "'Factorise fully' means you must take out both the highest common numerical factor and all algebraic factors.",
  },
  "simplify": {
    meaning: "Combine like terms and reduce to lowest terms.",
    examinerTip: "Never stop halfway. Cancel down common algebraic and numeric factors completely.",
  },
  "estimate": {
    meaning: "Work out an approximate value using reasonable approximations.",
    examinerTip: "Usually round each number to 1 significant figure before computing.",
  },
  "determine": {
    meaning: "Establish key facts, values, or solutions with necessary working.",
    examinerTip: "Show the logical or mathematical basis behind your deduction.",
  },
  "find": {
    meaning: "A general command: calculate, read from a graph, or deduce algebraically.",
    examinerTip: "Look at the mark allocation: 1 mark usually means read directly; 2+ marks requires showing method.",
  },
};

export function getCommandWordInfo(word: string | null | undefined): CommandWordInfo | null {
  if (!word) return null;
  const key = word.trim().toLowerCase();
  return COMMAND_WORDS[key] ?? null;
}
