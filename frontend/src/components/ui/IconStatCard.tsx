type IconStatCardProps = {
  icon: string;
  label: string;
  value: string;
};

export default function IconStatCard({
  icon,
  label,
  value,
}: IconStatCardProps) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-[#135bec]/10 text-[#135bec]">
        <span className="material-symbols-outlined">{icon}</span>
      </div>
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{value}</p>
    </div>
  );
}