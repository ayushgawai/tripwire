"use client";
export function ErrorToast({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="fixed bottom-4 left-1/2 z-50 w-[min(92vw,520px)] -translate-x-1/2 animate-rise rounded-2xl border border-danger/30 bg-card px-4 py-3 text-sm text-danger shadow-xl">
      <b className="mr-1">Problem:</b>
      {message}
    </div>
  );
}
