import { AppShell } from "@/components/AppShell";

export default function ParentLayout({ children }: { children: React.ReactNode }) {
  return <AppShell audience="parent">{children}</AppShell>;
}
