"use client";

export interface FamilyJoinPanelProps {
  alertSummary?: string | null;
  evidenceQuotes?: string[];
  joining?: boolean;
  joined?: boolean;
  familyInControl?: boolean;
  onJoin?: () => void;
}

export function FamilyJoinPanel({
  alertSummary,
  evidenceQuotes = [],
  joining,
  joined,
  familyInControl,
  onJoin,
}: FamilyJoinPanelProps) {
  return (
    <section aria-label="Family join" data-testid="family-join-panel">
      <h2 style={{ fontSize: "1.1rem" }}>Family alert</h2>
      <p>
        {alertSummary ??
          "Tripwire paused a call for family verification. Review evidence, then join."}
      </p>
      {evidenceQuotes.length > 0 ? (
        <div>
          <h3 style={{ fontSize: "0.95rem" }}>Evidence</h3>
          <ul>
            {evidenceQuotes.map((q) => (
              <li key={q}>“{q}”</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>
          Evidence will appear here when the backend supplies quoted statements.
        </p>
      )}
      <p aria-live="polite" style={{ fontWeight: 700 }}>
        Status:{" "}
        {familyInControl
          ? "Family in control"
          : joined
            ? "Joined — confirming control"
            : joining
              ? "Joining…"
              : "Not joined"}
      </p>
      {!joined ? (
        <button type="button" onClick={onJoin} disabled={joining}>
          {joining ? "Joining…" : "Join"}
        </button>
      ) : (
        <p>You are in the call. AI assistant speech has stopped.</p>
      )}
    </section>
  );
}
