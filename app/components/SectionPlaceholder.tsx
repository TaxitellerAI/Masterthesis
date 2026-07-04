"use client";

// Uniform placeholder for result sections: a quiet skeleton shimmer while the
// engine computes, a plain hairline box when there is genuinely no data.
export default function SectionPlaceholder({
  loading,
  label,
  height = 180,
}: {
  loading: boolean;
  label?: string;
  height?: number;
}) {
  if (loading) {
    return (
      <div className="skeleton flex items-end p-4" style={{ height }} aria-busy>
        {label && <span className="text-faint text-xs relative z-10">{label}</span>}
      </div>
    );
  }
  return (
    <div className="border border-hairline bg-paper py-12 text-center text-faint text-sm">
      Keine Daten.
    </div>
  );
}
