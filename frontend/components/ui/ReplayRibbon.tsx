/** Mandatory label whenever fixtures drive the UI (plan: "visibly labeled Demo replay"). */
export function ReplayRibbon() {
  return (
    <div className="sticky top-0 z-50 flex items-center justify-center gap-2 bg-ai px-4 py-1.5 text-center text-xs font-bold uppercase tracking-[0.2em] text-white">
      Demo replay · fixture events · not live inference
    </div>
  );
}
