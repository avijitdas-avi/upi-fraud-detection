import type { Decision, DecisionStats, ScoreTransactionInput } from "./types";

// Set NEXT_PUBLIC_API_URL in .env.local (or your Vercel project's
// environment variables) to point at your deployed FastAPI backend.
// Falls back to localhost for local development against a backend
// running on your own machine.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`Request to ${path} failed (${response.status}): ${body}`);
  }

  return response.json();
}

export function getStats(): Promise<DecisionStats> {
  return apiFetch<DecisionStats>("/api/decisions/stats");
}

export function getRecentDecisions(limit: number = 50): Promise<Decision[]> {
  return apiFetch<Decision[]>(`/api/decisions/recent?limit=${limit}`);
}

export function scoreTransaction(input: ScoreTransactionInput): Promise<Decision> {
  return apiFetch<Decision>("/score", {
    method: "POST",
    body: JSON.stringify(input),
  });
}
