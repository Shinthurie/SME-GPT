export default function StatusBar() {
  return (
    <div className="h-12 w-full flex justify-between items-center px-6 bg-background-light dark:bg-background-dark sticky top-0 z-50">
      <span className="text-sm font-semibold">9:41</span>
      <div className="flex space-x-1.5 items-center">
        <span className="material-icons text-sm">signal_cellular_alt</span>
        <span className="material-icons text-sm">wifi</span>
        <span className="material-icons text-sm rotate-90">
          battery_full
        </span>
      </div>
    </div>
  );
}