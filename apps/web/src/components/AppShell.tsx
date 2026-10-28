"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, type Me } from "@/lib/api";
import { localSignInEnabled } from "@/lib/auth";
import { devSignIn, type DevRole } from "@/lib/devAuth";
import { clearToken, getToken } from "@/lib/session";
import { AskBox } from "./AskBox";
import { Icon, type IconName } from "./icons";

const MeContext = createContext<Me | null>(null);
export const useMe = () => useContext(MeContext);

type ThemeMode = "light" | "dark";
const THEME_STORAGE_KEY = "scholr:theme-mode:v1";

type NavItem = { href: string; label: string; icon: IconName; badge?: string };
type NavGroup = { section?: string; items: NavItem[] };

// The student and guardian menus. Labels are ours; no other product is named here.
const STUDENT_NAV: NavGroup[] = [
  { items: [{ href: "/student", label: "Today", icon: "home" }] },
  {
    section: "Study",
    items: [
      { href: "/student/learn", label: "Subjects", icon: "learn" },
      { href: "/student/practice/daily", label: "Today's set", icon: "check" },
      { href: "/student/homework", label: "My homework", icon: "notes" },
      { href: "/student/practice", label: "Question bank", icon: "practice" },
      { href: "/student/notebooks", label: "My notebooks", icon: "notes" },
      { href: "/student/tutor", label: "Tutor", icon: "tutor" },
      { href: "/student/iit", label: "IIT classes", icon: "external" },
    ],
  },
  {
    section: "How I'm doing",
    items: [
      { href: "/student/progress", label: "My progress", icon: "progress" },
      { href: "/student/mistakes", label: "My mistakes", icon: "mistakes" },
    ],
  },
  {
    section: "Exams and papers",
    items: [
      { href: "/student/examinations", label: "Mock exams", icon: "tests" },
      { href: "/student/papers", label: "Past papers", icon: "clock" },
      { href: "/student/tests", label: "Tests set for me", icon: "tests" },
    ],
  },
  {
    section: "Privacy",
    items: [
      { href: "/student/visibility", label: "What my parents see", icon: "visibility" },
      { href: "/consent", label: "Privacy", icon: "privacy" },
    ],
  },
];

const PARENT_NAV: NavGroup[] = [
  { items: [{ href: "/parent", label: "Executive Overview", icon: "home" }] },
  {
    section: "Progress",
    items: [
      { href: "/parent/summary", label: "Monthly Analytics", icon: "progress" },
      { href: "/parent/review", label: "Mark Verification", icon: "check" },
      { href: "/parent/examinations", label: "Mock Examinations", icon: "tests" },
      { href: "/parent/tests", label: "Test Series & Study", icon: "tests" },
      { href: "/parent/schedule", label: "Timetable & Rhythm", icon: "schedule" },
      { href: "/parent/iit", label: "IIT Foundation Standing", icon: "external" },
      { href: "/parent/notes", label: "Learning Notes", icon: "notes" },
    ],
  },
  {
    section: "Safety",
    items: [
      { href: "/parent/safety", label: "Safety Telemetry", icon: "shield" },
      { href: "/consent", label: "Privacy", icon: "privacy" },
    ],
  },
];

function Logo({ portal, isStudent }: { portal: string; isStudent: boolean }) {
  return (
    <div className="flex items-center gap-3 px-2 py-1.5">
      <div className="h-10 w-10 flex-none rounded-xl bg-gradient-to-br from-blue-500 via-indigo-500 to-emerald-400 flex items-center justify-center text-white shadow-md shadow-blue-600/25 font-mono text-lg font-extrabold">
        S
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-base font-extrabold tracking-tight text-white">
            SCHOLR
          </span>
          <span className="inline-block px-1.5 py-0.5 font-mono text-[10px] font-bold rounded bg-blue-500/20 text-blue-300 border border-blue-400/30">
            {isStudent ? "PRO · Y10" : "GUARDIAN"}
          </span>
        </div>
        <div className="text-[11px] text-slate-400 font-medium truncate">
          {portal}
        </div>
      </div>
    </div>
  );
}

export function AppShell({ audience, children }: { audience: "student" | "parent"; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const [switchable, setSwitchable] = useState(true);
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY) as ThemeMode | null;
      if (saved === "dark" || saved === "light") {
        setTheme(saved);
        document.documentElement.dataset.theme = saved;
      } else {
        document.documentElement.dataset.theme = "light";
      }
    } catch {
      // ignore storage errors
    }
  }, []);

  function selectTheme(next: ThemeMode) {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }

  // The Student/Parent switch opens a seeded account, which exists in development mode only.
  useEffect(() => {
    localSignInEnabled()
      .then((local) => setSwitchable(!local))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/");
      return;
    }
    api<Me>("/me")
      .then((value) => {
        const isStudent = value.user.role === "student";
        if (value.user.role === "admin") router.replace("/admin/registrations");
        else if (audience === "student" && !isStudent) router.replace("/parent");
        else if (audience === "parent" && isStudent) router.replace("/student");
        else setMe(value);
      })
      .catch(() => {
        clearToken();
        router.replace("/");
      });
  }, [audience, router]);

  const nav = audience === "student" ? STUDENT_NAV : PARENT_NAV;
  const activeHref = nav
    .flatMap((g) => g.items.map((i) => i.href))
    .filter((href) => href === pathname || (href !== `/${audience}` && pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.length - a.length)[0];
  const name = me?.user.display_name ?? "";
  const isStudent = audience === "student";

  const topShortcuts = isStudent
    ? [
        { href: "/student", label: "Today", icon: "◫" },
        { href: "/student/learn", label: "Subjects", icon: "📖" },
        { href: "/student/practice", label: "Questions", icon: "✍️" },
        { href: "/student/tutor", label: "Tutor", icon: "⚡" },
        { href: "/student/iit", label: "IIT", icon: "🏛️" },
        { href: "/student/progress", label: "Progress", icon: "📈" },
      ]
    : [
        { href: "/parent", label: "Overview", icon: "◫" },
        { href: "/parent/summary", label: "Monthly", icon: "📈" },
        { href: "/parent/review", label: "Verify Marks", icon: "✓" },
        { href: "/parent/schedule", label: "Timetable", icon: "🕒" },
        { href: "/parent/safety", label: "Safety", icon: "🛡️" },
      ];

  return (
    <MeContext.Provider value={me}>
      <div className="flex min-h-screen bg-[var(--color-ground)] text-[var(--color-ink)]">
        {/* Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 flex w-68 flex-col border-r border-slate-800/80 bg-[#0B1528] text-slate-100 p-4 transition-transform md:static md:translate-x-0 ${
            open ? "translate-x-0 shadow-2xl" : "-translate-x-full"
          }`}
        >
          <Logo
            portal={isStudent ? "Cambridge CIE & IIT Studio" : "Academic Telemetry & Oversight"}
            isStudent={isStudent}
          />

          <nav className="mt-5 flex flex-1 flex-col gap-1 overflow-y-auto pr-1">
            {nav.map((group) => (
              <div key={group.section ?? "top"} className="flex flex-col gap-1">
                {group.section && (
                  <div className="mt-4 px-3 font-mono text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                    {group.section}
                  </div>
                )}
                {group.items.map((item) => {
                  const active = item.href === activeHref;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setOpen(false)}
                      className={`flex h-9.5 items-center justify-between gap-2.5 rounded-xl px-3 text-xs font-semibold transition-all ${
                        active
                          ? "bg-blue-600 text-white shadow-md shadow-blue-600/25 font-bold"
                          : "text-slate-300 hover:text-white hover:bg-white/5"
                      }`}
                    >
                      <span className="flex items-center gap-2.5 min-w-0">
                        <Icon
                          name={item.icon}
                          className={`h-[17px] w-[17px] shrink-0 ${active ? "text-white" : "text-blue-400/80"}`}
                        />
                        <span className="truncate">{item.label}</span>
                      </span>
                      {item.badge && (
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono text-[9px] font-bold ${
                            active
                              ? "bg-blue-800 text-blue-100"
                              : "bg-emerald-500/15 text-emerald-300 border border-emerald-400/25"
                          }`}
                        >
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* Bottom Academic Telemetry Status Card */}
          <div className="mt-auto pt-3">
            <div className="rounded-2xl border border-blue-500/25 bg-gradient-to-br from-blue-950/90 via-slate-900 to-indigo-950/90 p-3.5 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-bold text-white">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span>{isStudent ? "Dual-Engine Verified" : "Guardian Co-Pilot"}</span>
                </span>
                <span className="font-mono text-[10px] font-bold text-blue-300">
                  {isStudent ? "v6.0" : "LIVE"}
                </span>
              </div>
              <p className="text-[10.5px] text-slate-300 leading-relaxed">
                {isStudent
                  ? "Cambridge 0495 / 0580 / 0625 Mark Schemes + SymPy Symbolic Verification"
                  : "Real-time syllabus mastery & independent attempt telemetry"}
              </p>
            </div>
          </div>
        </aside>

        {open && (
          <button
            aria-label="Close menu"
            className="fixed inset-0 z-30 bg-slate-950/60 backdrop-blur-xs md:hidden"
            onClick={() => setOpen(false)}
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top Sticky Command Bar */}
          <header
            className={`sticky top-0 z-30 flex h-15 items-center gap-3 border-b px-4 md:px-6 backdrop-blur-md transition-colors ${
              theme === "dark"
                ? "border-slate-800 bg-[#090D16]/90"
                : "border-slate-200/90 bg-white/95 shadow-2xs"
            }`}
          >
            <button
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-300 bg-slate-100 text-slate-800 font-bold md:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open navigation menu"
            >
              ☰
            </button>

            {/* Quick Navigation Chips on desktop */}
            <div className="hidden xl:flex items-center gap-1 rounded-xl border border-slate-200/80 bg-slate-100/80 p-1 text-xs font-semibold">
              {topShortcuts.map((chip) => {
                const active =
                  chip.href === pathname || (chip.href !== `/${audience}` && pathname.startsWith(chip.href));
                return (
                  <Link
                    key={chip.href}
                    href={chip.href}
                    className={`px-2.5 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
                      active
                        ? "bg-blue-600 text-white shadow-2xs font-bold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-white/80"
                    }`}
                  >
                    <span className="text-xs">{chip.icon}</span>
                    <span>{chip.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* Student Search / Master Router Ask Bar */}
            {isStudent && me && (
              <div className="hidden flex-1 max-w-xs md:block">
                <AskBox />
              </div>
            )}

            <div className="ml-auto flex items-center gap-2.5">
              {/* Theme switcher: light or dark */}
              <div
                className="flex items-center gap-1 rounded-xl border border-slate-200/90 bg-slate-100/90 p-1 text-[11px] font-bold"
                role="group"
                aria-label="Visual theme"
              >
                <button
                  type="button"
                  onClick={() => selectTheme("light")}
                  className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                    theme === "light"
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                  title="Light theme"
                >
                  ☀️ Light
                </button>
                <button
                  type="button"
                  onClick={() => selectTheme("dark")}
                  className={`rounded-lg px-2.5 py-1 transition cursor-pointer ${
                    theme === "dark"
                      ? "bg-blue-600 text-white shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                  title="Dark Focus Studio Theme"
                >
                  🌙 Dark
                </button>
              </div>

              {/* User Avatar & Name */}
              <div className="hidden sm:flex items-center gap-2 rounded-xl border border-slate-200/90 bg-slate-50 pl-1.5 pr-3 py-1">
                <div className="h-7 w-7 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center text-white font-mono font-bold text-xs shadow-inner">
                  {isStudent ? "Y10" : "GD"}
                </div>
                <div className="text-left">
                  <div className="text-xs font-bold text-slate-900 leading-tight truncate max-w-[115px]">
                    {name || (isStudent ? "Student" : "Guardian")}
                  </div>
                  <div className="font-mono text-[10px] text-slate-400 font-semibold leading-none">
                    {isStudent ? (me?.student?.year_group ?? "Year 10") : "Guardian"}
                  </div>
                </div>
              </div>

              {!switchable && (
                <button
                  onClick={() => {
                    clearToken();
                    router.replace("/sign-in");
                  }}
                  className="rounded-xl border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-600 transition-all hover:text-slate-900 cursor-pointer"
                >
                  Sign out
                </button>
              )}

              {/* Role Switcher */}
              {switchable && (
                <div
                  className="flex items-center gap-1 rounded-xl border border-slate-200/90 bg-slate-100/90 p-1"
                  role="group"
                  aria-label="View as"
                >
                  {(
                    [
                      { role: "student", label: "Student", href: "/student" },
                      { role: "guardian", label: "Guardian", href: "/parent" },
                    ] as { role: DevRole; label: string; href: string }[]
                  ).map((option) => {
                    const active = (audience === "student") === (option.role === "student");
                    return (
                      <button
                        key={option.role}
                        aria-pressed={active}
                        onClick={async () => {
                          if (active) return;
                          try {
                            await devSignIn(option.role);
                            router.replace(option.href);
                          } catch {
                            setSwitchable(false);
                          }
                        }}
                        className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition-all cursor-pointer ${
                          active
                            ? "bg-slate-900 text-white shadow-2xs"
                            : "text-slate-600 hover:text-slate-900"
                        }`}
                      >
                        {option.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </header>

          {/* Main Content Area */}
          <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
            {me ? (
              children
            ) : (
              <div className="flex h-64 items-center justify-center">
                <div className="flex items-center gap-3.5 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 font-mono text-base font-extrabold text-white animate-pulse">
                    S
                  </div>
                  <div>
                    <div className="text-sm font-bold text-slate-900">Initialising Scholr Pro Workspace…</div>
                    <div className="text-xs text-slate-500">Loading Cambridge CIE &amp; IIT Foundation telemetry</div>
                  </div>
                </div>
              </div>
            )}
          </main>
        </div>
      </div>
    </MeContext.Provider>
  );
}
