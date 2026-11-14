"use client";

import type { CallParticipant } from "./types";

export interface ParticipantListProps {
  participants: CallParticipant[];
}

export function ParticipantList({ participants }: ParticipantListProps) {
  return (
    <section aria-label="Participants">
      <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Participants</h2>
      {participants.length === 0 ? (
        <p>No participants yet.</p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {participants.map((p) => (
            <li
              key={p.id}
              data-testid={`participant-${p.id}`}
              style={{
                borderBottom: "1px solid #444",
                padding: "0.4rem 0",
                display: "flex",
                justifyContent: "space-between",
                gap: "1rem",
              }}
            >
              <span>
                {p.displayName}
                {p.local ? " (you)" : ""}
                {p.role ? ` · ${p.role}` : ""}
              </span>
              <span aria-label="Audio status">
                {p.local
                  ? p.micPublishing
                    ? "Mic on"
                    : "Mic paused"
                  : p.audioSubscribed
                    ? "Hearing"
                    : "Audio blocked"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
