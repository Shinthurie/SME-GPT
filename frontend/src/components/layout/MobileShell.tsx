export default function MobileShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text-1)" }}>
      {children}
    </div>
  );
}
