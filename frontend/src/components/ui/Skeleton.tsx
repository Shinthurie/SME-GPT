/**
 * Skeleton — pulsing placeholder blocks.
 *
 * A page that gates its whole render on an async check used to return null,
 * which paints nothing at all: on mobile you saw the bare body background —
 * white or black depending on theme — and then the page appeared. Rendering the
 * page's own chrome with these standing in for the data keeps the frame on
 * screen the whole time, which is what makes a transition read as an app rather
 * than a reload.
 *
 * The visual language (animate-pulse, var(--border) fill) matches the
 * placeholders the dashboard already used for its summary, so a page that is
 * partly loaded doesn't mix two different idioms.
 */

export function Skeleton({
  className = "",
  rounded = "rounded-md",
}: {
  className?: string;
  rounded?: string;
}) {
  return (
    <div
      className={`animate-pulse ${rounded} ${className}`}
      style={{ background: "var(--border)" }}
      aria-hidden
    />
  );
}

/** A card-shaped placeholder: the surface and border are real, only the
 *  contents pulse — so the layout doesn't shift when the data lands. */
export function SkeletonCard({
  lines = 3,
  className = "",
}: {
  lines?: number;
  className?: string;
}) {
  const widths = ["w-1/2", "w-3/4", "w-2/5", "w-2/3", "w-1/3"];
  return (
    <div
      className={`rounded-2xl p-4 ${className}`}
      style={{ background: "var(--surface)", border: "1px solid var(--border)" }}
    >
      <div className="space-y-2.5">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} className={`h-[13px] ${widths[i % widths.length]}`} />
        ))}
      </div>
    </div>
  );
}

/**
 * The generic "page is coming" body: a few cards' worth of placeholder.
 * Rendered *inside* a page's real shell, never instead of it.
 */
export function PageBodySkeleton({ cards = 3 }: { cards?: number }) {
  return (
    <div
      className="space-y-3"
      role="status"
      aria-busy="true"
      aria-label="Loading"
    >
      {Array.from({ length: cards }).map((_, i) => (
        <SkeletonCard key={i} lines={i === 0 ? 4 : 3} />
      ))}
    </div>
  );
}
