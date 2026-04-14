export default function MobileShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="min-h-screen bg-[#f6f7fb]">{children}</div>;
}