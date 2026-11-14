// Local fixture scenarios for development and the labeled "Demo replay" mode.
// These are NOT live inference. Every page that renders them shows a "Demo replay" badge.
// Scenarios mirror the "Checks before recording" list in the build plan.
import type { EventType } from "./types.ts";

export interface FixtureStep {
  /** ms after the previous step */
  delay: number;
  type: EventType;
  payload: Record<string, unknown>;
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  steps: FixtureStep[];
}

const say = (delay: number, id: string, speaker: string, text: string): FixtureStep => ({
  delay,
  type: "transcript.final",
  payload: { utterance_id: id, speaker, text },
});

const SCAM_EVIDENCE = [
  { utterance_id: "utt_001", quote: "Buy $500 in gift cards now" },
  { utterance_id: "utt_001", quote: "Please do not tell anyone" },
  { utterance_id: "utt_003", quote: "There is no time" },
];

export const SCENARIOS: Scenario[] = [
  {
    id: "scam",
    title: "Gift card scam",
    description: "Gift cards + urgency + secrecy → takeover, family alert, daughter joins.",
    steps: [
      say(900, "utt_001", "caller", "Grandma, I am in trouble. Buy $500 in gift cards now. Please do not tell anyone."),
      {
        delay: 900,
        type: "risk.updated",
        payload: {
          decision_id: "decision_001",
          risk: "review",
          reasons: ["gift_card_request", "secrecy"],
          evidence: SCAM_EVIDENCE.slice(0, 2),
          summary: "The caller requests gift cards and asks the wearer to keep it secret.",
          recommended_action: "alert",
        },
      },
      say(1600, "utt_002", "wearer", "Should I call your mother?"),
      say(1500, "utt_003", "caller", "No. There is no time."),
      {
        delay: 1000,
        type: "risk.updated",
        payload: {
          decision_id: "decision_002",
          risk: "high",
          reasons: ["gift_card_request", "urgency", "secrecy", "discourages_verification"],
          evidence: SCAM_EVIDENCE,
          summary:
            "The caller demands gift cards urgently, asks for secrecy, and refuses family verification.",
          recommended_action: "takeover",
        },
      },
      { delay: 300, type: "takeover.started", payload: { decision_id: "decision_002" } },
      {
        delay: 400,
        type: "family.alert",
        payload: {
          decision_id: "decision_002",
          summary:
            "The caller demands gift cards urgently, asks for secrecy, and refuses family verification.",
          reasons: ["gift_card_request", "urgency", "secrecy", "discourages_verification"],
          evidence: SCAM_EVIDENCE,
        },
      },
      { delay: 1100, type: "takeover.active", payload: { decision_id: "decision_002" } },
      say(
        600,
        "utt_004",
        "assistant",
        "I am Tripwire, an AI assistant. This conversation has been paused for family verification. Please explain your request.",
      ),
      say(2600, "utt_005", "caller", "It has to happen now."),
      say(1400, "utt_006", "assistant", "A family member will verify the request before anyone acts."),
    ],
  },
  {
    id: "benign",
    title: "Benign call",
    description: "“Please call me back tomorrow.” → stays in monitoring.",
    steps: [
      say(900, "utt_001", "caller", "Hi, it's the pharmacy. Please call me back tomorrow."),
      say(1500, "utt_002", "wearer", "Okay, thank you. I will."),
      {
        delay: 900,
        type: "risk.updated",
        payload: {
          decision_id: "decision_001",
          risk: "low",
          reasons: [],
          evidence: [],
          summary: "Routine callback request. No concerning patterns.",
          recommended_action: "none",
        },
      },
    ],
  },
  {
    id: "ambiguous",
    title: "Ambiguous charge",
    description: "“The service costs $2,000.” → review at most, no takeover.",
    steps: [
      say(900, "utt_001", "caller", "The service costs $2,000."),
      say(1500, "utt_002", "wearer", "That's more than I expected. Let me think about it."),
      {
        delay: 900,
        type: "risk.updated",
        payload: {
          decision_id: "decision_001",
          risk: "review",
          reasons: ["large_amount"],
          evidence: [{ utterance_id: "utt_001", quote: "The service costs $2,000." }],
          summary: "A large price was mentioned, with no pressure or secrecy. Worth a second look only.",
          recommended_action: "none",
        },
      },
    ],
  },
];

export function getScenario(id: string | null | undefined): Scenario {
  return SCENARIOS.find((s) => s.id === id) ?? SCENARIOS[0];
}

/** Steps synthesized in replay when the family member presses Join / Reconnect. */
export const REPLAY_FAMILY_JOIN: FixtureStep[] = [
  { delay: 1200, type: "family.joined", payload: { participant: "family" } },
  say(900, "utt_fam_1", "family", "Mom, pause. I will call him on the number we already know."),
];
export const REPLAY_RECONNECT: FixtureStep[] = [
  { delay: 600, type: "wearer.reconnected", payload: {} },
];
export const REPLAY_END: FixtureStep[] = [{ delay: 200, type: "session.ended", payload: {} }];
