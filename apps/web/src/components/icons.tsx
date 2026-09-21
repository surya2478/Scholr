// Line icons used across the app (design/home). One stroke weight, currentColor, no icon library.
export type IconName =
  | "home"
  | "practice"
  | "tutor"
  | "progress"
  | "mistakes"
  | "tests"
  | "visibility"
  | "privacy"
  | "calendar"
  | "clock"
  | "check"
  | "spark"
  | "repair"
  | "flag"
  | "shield"
  | "notes"
  | "schedule"
  | "external"
  | "learn";

const PATHS: Record<IconName, React.ReactNode> = {
  learn: <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5Zm16 0A1.5 1.5 0 0 0 18.5 4H13v16h5.5a1.5 1.5 0 0 0 1.5-1.5Z" />,
  home: <path d="M3.5 10.5 12 4l8.5 6.5V19a1 1 0 0 1-1 1H15v-5H9v5H4.5a1 1 0 0 1-1-1Z" />,
  // Learning that happens outside Scholr: a door out of the building.
  external: (
    <>
      <path d="M13.5 4.5H6a1.5 1.5 0 0 0-1.5 1.5v12A1.5 1.5 0 0 0 6 19.5h7.5" />
      <path d="M16 8.5 19.5 12 16 15.5" />
      <path d="M19 12h-9" />
    </>
  ),
  practice: (
    <>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  tutor: <path d="M20 14.5a2 2 0 0 1-2 2H9l-4 3.5v-3.5H6a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2Z" />,
  progress: (
    <>
      <path d="M4 20h16" />
      <path d="M7 20v-6M12 20V8M17 20v-9" />
    </>
  ),
  mistakes: (
    <>
      <path d="M12 4.5 21 19.5H3Z" />
      <path d="M12 10v4M12 16.8v.2" />
    </>
  ),
  tests: (
    <>
      <path d="M8 5h8a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z" />
      <path d="M10 4h4v3h-4zM9.5 12l1.8 1.8 3.4-3.4" />
    </>
  ),
  visibility: (
    <>
      <path d="M2.8 12S6 6.5 12 6.5 21.2 12 21.2 12 18 17.5 12 17.5 2.8 12 2.8 12Z" />
      <circle cx="12" cy="12" r="2.6" />
    </>
  ),
  privacy: (
    <>
      <path d="M7 10.5V8a5 5 0 0 1 10 0v2.5" />
      <rect x="5" y="10.5" width="14" height="9.5" rx="2" />
    </>
  ),
  calendar: (
    <>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2" />
      <path d="M4 10h16M9 3.5v4M15 3.5v4" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5V12l3 2" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M8.5 12.2l2.4 2.4 4.6-5" />
    </>
  ),
  spark: <path d="M12 4l1.9 5.1L19 11l-5.1 1.9L12 18l-1.9-5.1L5 11l5.1-1.9Z" />,
  repair: <path d="M14.5 5.5a4 4 0 0 0 5 5L14 16l-2.5-2.5Zm-3.7 8.2L6 18.5 5.5 20l1.5-.5 4.8-4.8" />,
  flag: (
    <>
      <path d="M6 20V5" />
      <path d="M6 5.5h10l-2 3 2 3H6Z" />
    </>
  ),
  shield: <path d="M12 3.5 19 6v6c0 4-3 6.8-7 8.5C8 18.8 5 16 5 12V6Z" />,
  notes: (
    <>
      <rect x="5" y="4" width="14" height="16" rx="2" />
      <path d="M8.5 9h7M8.5 12.5h7M8.5 16h4" />
    </>
  ),
  schedule: (
    <>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2" />
      <path d="M4 10h16M8.5 14h3M8.5 17h7" />
    </>
  ),
};

export function Icon({ name, className = "h-[18px] w-[18px]" }: { name: IconName; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {PATHS[name]}
    </svg>
  );
}
