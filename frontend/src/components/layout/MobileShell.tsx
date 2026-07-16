import QuickActions from "./QuickActions";

export default function MobileShell({
  children,
  hideQuickActions = false,
}: {
  children: React.ReactNode;
  /** Suppress the floating Quick Actions button — for pages with their own
   * fixed bottom UI (e.g. a chat input bar) that would collide with it. */
  hideQuickActions?: boolean;
}) {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text-1)" }}>
      {children}
      {!hideQuickActions && <QuickActions />}
    </div>
  );
}
