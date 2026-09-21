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

type NavItem = { href: string; label: string; icon: IconName };
type NavGroup = { section?: string; items: NavItem[] };

// Grouped like design/home: a home link, then sections. Learn opens the streams (docs/STUDENT-APP.md): subject →
// chapter → topic. The Tutor is the one assistant; it clears doubts where she is stuck.
const STUDENT_NAV: NavGroup[] = [
  { items: [{ href: "/student", label: "Home", icon: "home" }] },
  {
    section: "LEARN",
    items: [
      { href: "/student/learn", label: "Subjects & topics", icon: "learn" },
      { href: "/student/practice/daily", label: "Today's practice", icon: "check" },
      { href: "/student/practice", label: "Practice", icon: "practice" },
      { href: "/student/tutor", label: "Ask the Tutor", icon: "tutor" },
      { href: "/student/iit", label: "IIT Foundation", icon: "external" },
    ],
  },
  {
    section: "PROGRESS",
    items: [
      { href: "/student/progress", label: "My Progress", icon: "progress" },
      { href: "/student/mistakes", label: "My Mistakes", icon: "mistakes" },
    ],
  },
  {
    section: "ASSESSMENTS",
    items: [
      { href: "/student/papers", label: "Timed past papers", icon: "clock" },
      { href: "/student/tests", label: "Tests", icon: "tests" },
    ],
  },
  {
    section: "PRIVACY",
    items: [
      { href: "/student/visibility", label: "What my parent sees", icon: "visibility" },
      { href: "/consent", label: "Privacy & consent", icon: "privacy" },
    ],
  },
];

const PARENT_NAV: NavGroup[] = [
  { items: [{ href: "/parent", label: "Overview", icon: "home" }] },
  {
    section: "PROGRESS",
    items: [
      { href: "/parent/summary", label: "Monthly summary", icon: "progress" },
      { href: "/parent/review", label: "Review marks", icon: "check" },
      { href: "/parent/tests", label: "Tests & study", icon: "tests" },
      { href: "/parent/schedule", label: "Schedule", icon: "schedule" },
      { href: "/parent/iit", label: "IIT Foundation", icon: "external" },
      { href: "/parent/notes", label: "Learning notes", icon: "notes" },
    ],
  },
  {
    section: "SAFETY & PRIVACY",
    items: [
      { href: "/parent/safety", label: "Safety alerts", icon: "shield" },
      { href: "/consent", label: "Privacy & consent", icon: "privacy" },
    ],
  },
];

function Logo({ portal, isStudent }: { portal: string; isStudent: boolean }) {
  return (
    <div className="flex items-center gap-3 px-2 py-2">
      <div className="h-11 w-11 flex-none rounded-2xl bg-gradient-to-tr from-amber-500 via-orange-500 to-amber-400 flex items-center justify-center text-white shadow-md shadow-orange-500/20 text-2xl font-fun font-bold transform -rotate-2 hover:rotate-0 transition-transform">
        S
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="font-fun text-xl font-bold tracking-tight text-slate-900">
            Scholr<span className="text-orange-500">{isStudent ? "Jr" : "Family"}</span>
          </span>
          <span className="hidden xl:inline-block px-2 py-0.5 text-[10px] font-bold rounded-full bg-orange-100 text-orange-700 border border-orange-200">
            {isStudent ? "Year 10" : "Guardian"}
          </span>
        </div>
        <div className="text-[10.5px] text-slate-500 font-medium truncate">
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

  // The Student/Parent switch opens a seeded account, which exists in development mode only: with real
  // accounts (docs/STUDENT-APP.md D7) each person signs in as themselves.
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
  // The most specific entry wins: /student/practice/daily lights "Today's practice", not "Practice" as well.
  const activeHref = nav
    .flatMap((g) => g.items.map((i) => i.href))
    .filter((href) => href === pathname || (href !== `/${audience}` && pathname.startsWith(`${href}/`)))
    .sort((a, b) => b.length - a.length)[0];
  const name = me?.user.display_name ?? "";
  const isStudent = audience === "student";

  // Top header quick navigation shortcuts
  const topShortcuts = isStudent
    ? [
        { href: "/student", label: "Adventure", icon: "🌟" },
        { href: "/student/learn", label: "Learn", icon: "📚" },
        { href: "/student/practice", label: "Practice", icon: "📐" },
        { href: "/student/tutor", label: "Tutor", icon: "🦉" },
        { href: "/student/iit", label: "IIT Bridge", icon: "⚡" },
        { href: "/student/progress", label: "Progress", icon: "🏆" },
      ]
    : [
        { href: "/parent", label: "Overview", icon: "☀️" },
        { href: "/parent/summary", label: "Monthly", icon: "📅" },
        { href: "/parent/review", label: "Review Marks", icon: "✏️" },
        { href: "/parent/schedule", label: "Schedule", icon: "🕒" },
        { href: "/parent/safety", label: "Safety", icon: "🛡️" },
      ];

  return (
    <MeContext.Provider value={me}>
      <div className="flex min-h-screen bg-[#FBF9F5]">
        {/* Warm Friendly Sidebar */}
        <aside
          className={`fixed inset-y-0 left-0 z-40 flex w-68 flex-col border-r-2 border-amber-100 bg-white p-4 transition-transform md:static md:translate-x-0 ${
            open ? "translate-x-0 shadow-2xl" : "-translate-x-full"
          }`}
        >
          <Logo portal={isStudent ? "Smart, Fun & Cambridge Verified! 🚀" : "Family Co-Pilot & Oversight"} isStudent={isStudent} />
          
          <nav className="mt-5 flex flex-1 flex-col gap-1 overflow-y-auto pr-1">
            {nav.map((group) => (
              <div key={group.section ?? "top"} className="flex flex-col gap-1">
                {group.section && (
                  <div className="mt-4 px-3.5 text-[11px] font-bold tracking-wider text-amber-900/60 uppercase">
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
                      className={`flex h-10 items-center gap-3 rounded-2xl px-3.5 text-sm font-semibold transition-all ${
                        active
                          ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-sm shadow-orange-500/20"
                          : "text-slate-600 hover:text-slate-900 hover:bg-amber-50/70"
                      }`}
                    >
                      <Icon
                        name={item.icon}
                        className={`h-[19px] w-[19px] ${active ? "text-white" : "text-amber-600/70"}`}
                      />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* Cheerful Mascot Motivation Card at Sidebar Bottom */}
          <div className="mt-auto pt-3">
            <div className="rounded-2xl border-2 border-amber-200/80 bg-gradient-to-br from-amber-50 via-orange-50 to-amber-50 p-3 text-center">
              <span className="text-xl inline-block mb-1">
                {isStudent ? "🦉" : "👨‍👩‍👧"}
              </span>
              <p className="text-xs font-fun font-bold text-slate-800 leading-snug">
                {isStudent ? "Small steps. Real progress." : "Guide gently. Grow independence."}
              </p>
              <p className="text-[10px] text-amber-700/80 mt-0.5 font-medium">
                {isStudent ? "Cambridge IGCSE + IIT Bridge" : "Oversight without micromanagement"}
              </p>
            </div>
          </div>
        </aside>

        {open && (
          <button
            aria-label="Close menu"
            className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-xs md:hidden"
            onClick={() => setOpen(false)}
          />
        )}

        <div className="flex min-w-0 flex-1 flex-col">
          {/* Top Sticky Header */}
          <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-amber-100 bg-white/95 backdrop-blur px-4 md:px-6 shadow-2xs">
            <button
              className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-200 bg-amber-50 text-orange-600 font-bold md:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open navigation menu"
            >
              ☰
            </button>

            {/* Quick Navigation Chips (CuriousJr style) on desktop */}
            <div className="hidden lg:flex items-center gap-1.5 bg-amber-50/80 p-1.5 rounded-2xl border border-amber-200/60 text-xs font-semibold">
              {topShortcuts.map((chip) => {
                const active = chip.href === pathname || (chip.href !== `/${audience}` && pathname.startsWith(chip.href));
                return (
                  <Link
                    key={chip.href}
                    href={chip.href}
                    className={`px-3 py-1.5 rounded-xl transition-all flex items-center gap-1.5 ${
                      active
                        ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-xs font-bold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-white/70"
                    }`}
                  >
                    <span>{chip.icon}</span>
                    <span>{chip.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* Student Search / Ask bar */}
            {isStudent && me && (
              <div className="hidden flex-1 max-w-xs md:block">
                <AskBox />
              </div>
            )}

            <div className="ml-auto flex items-center gap-3">
              {/* User Avatar & Name */}
              <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 pl-1.5 pr-3 py-1 rounded-full">
                <div className="h-8 w-8 rounded-full bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm shadow-inner">
                  {isStudent ? "👩‍🎓" : "👨‍👩‍👧"}
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-xs font-bold text-slate-800 leading-tight truncate max-w-[120px]">
                    {name || (isStudent ? "Student" : "Parent")}
                  </div>
                  <div className="text-[10px] text-slate-400 font-medium leading-none">
                    {isStudent ? (me?.student?.year_group ?? "Year 10") : "Parent account"}
                  </div>
                </div>
              </div>

              {!switchable && (
                <button
                  onClick={() => {
                    clearToken();
                    router.replace("/sign-in");
                  }}
                  className="rounded-full border border-amber-200 px-3 py-1 text-[11px] font-fun font-bold text-slate-600 transition-all hover:text-slate-900"
                >
                  Sign out
                </button>
              )}

              {/* Role Switcher */}
              {switchable && (
                <div className="flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50/60 p-1" role="group" aria-label="View as">
                  {(
                    [
                      { role: "student", label: "Student", href: "/student" },
                      { role: "guardian", label: "Parent", href: "/parent" },
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
                        className={`rounded-full px-3 py-1 text-[11px] font-fun font-bold transition-all ${
                          active
                            ? "bg-gradient-to-r from-orange-500 to-amber-500 text-white shadow-xs"
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
            {me ? children : (
              <div className="flex h-64 items-center justify-center">
                <div className="flex items-center gap-3 bg-white p-6 rounded-3xl border-2 border-amber-200 shadow-sm">
                  <div className="text-3xl animate-bounce">🦉</div>
                  <div>
                    <div className="text-sm font-fun font-bold text-slate-800">Opening your learning space…</div>
                    <div className="text-xs text-slate-400">Loading your adventure</div>
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
