// Thin REST/WS client for the Tripwire backend (contract table in the build plan).
// All provider credentials stay server side; this only ever sees short-lived room tokens.
import type { JoinCredentials, Role, SessionMode } from "./types.ts";

export const BACKEND_URL = (
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"
).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** Session access secret. Sent as a bearer token; the backend decides the exact scheme. */
function headers(token?: string | null): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) {
    h.Authorization = `Bearer ${token}`;
    h["X-Session-Token"] = token;
  }
  return h;
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${BACKEND_URL}${path}`, {
      ...rest,
      headers: { ...headers(token), ...(rest.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `Backend unreachable at ${BACKEND_URL}`);
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : typeof body === "string" && body
          ? body
          : res.statusText;
    throw new ApiError(res.status, `${res.status} ${detail}`);
  }
  return body as T;
}

export interface CreatedSession {
  session_id: string;
  state: string;
  /** Invite secret / scoped token if the backend issues one. */
  token?: string;
  invite?: string;
  [key: string]: unknown;
}

export const api = {
  createSession: (mode: SessionMode = "call") =>
    request<CreatedSession>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ mode, protection_enabled: true }),
    }),
  getSession: (id: string, token?: string | null) =>
    request<unknown>(`/api/sessions/${encodeURIComponent(id)}`, { token }),
  join: (id: string, role: Role, token?: string | null) =>
    request<JoinCredentials>(`/api/sessions/${encodeURIComponent(id)}/join`, {
      method: "POST",
      token,
      body: JSON.stringify({ role }),
    }),
  takeover: (id: string, decision_id: string, token?: string | null) =>
    request<{ accepted: boolean }>(`/api/sessions/${encodeURIComponent(id)}/takeover`, {
      method: "POST",
      token,
      body: JSON.stringify({ decision_id }),
    }),
  end: (id: string, token?: string | null) =>
    request<unknown>(`/api/sessions/${encodeURIComponent(id)}/end`, {
      method: "POST",
      token,
      body: "{}",
    }),
  /** PROPOSED endpoint — not in the frozen contract yet. Daughter hands audio back to the wearer. */
  reconnectWearer: (id: string, token?: string | null) =>
    request<unknown>(`/api/sessions/${encodeURIComponent(id)}/reconnect-wearer`, {
      method: "POST",
      token,
      body: "{}",
    }),
};

export function wsUrl(id: string, token?: string | null): string {
  const base = BACKEND_URL.replace(/^http/, "ws");
  const q = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${base}/ws/sessions/${encodeURIComponent(id)}${q}`;
}

export function tokenFrom(s: CreatedSession): string | undefined {
  return (s.token as string | undefined) ?? (s.invite as string | undefined);
}
