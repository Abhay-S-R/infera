/**
 * lib/api.ts — Centralized, typed API client for the Infera backend.
 *
 * All backend calls go through these functions so we have a single
 * place to update base URLs, add auth headers, or handle errors.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// ── Types ──────────────────────────────────────────

export interface HealthStats {
  active_workflows: number;
  total_reports: number;
  recent_completions: {
    competitor?: string;
    title?: string;
    completed_at?: string;
  }[];
}

export interface Competitor {
  id?: string;
  name: string;
}

export interface Report {
  id: string | number;
  title: string;
  competitor?: string;
  confidence?: number;
  created_at?: string;
}

export interface ReportDetail extends Report {
  documents?: Record<string, string>;
  full_report_markdown?: string;
  content?: string;
  markdown?: string;
}

export interface AnalyzeRequest {
  title: string;
  custom_question: string;
}

// ── Helpers ────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}

// ── Health ─────────────────────────────────────────

export async function fetchHealthStats(): Promise<HealthStats> {
  return apiFetch<HealthStats>("/api/health/stats");
}

// ── Competitors ────────────────────────────────────

export async function fetchCompetitors(): Promise<Competitor[]> {
  const data = await apiFetch<Competitor[] | { competitors: Competitor[] }>(
    "/api/competitors"
  );
  const list = Array.isArray(data)
    ? data
    : (data as { competitors: Competitor[] }).competitors || [];
  return list.map((c: string | Competitor) =>
    typeof c === "string"
      ? { name: c, id: c }
      : { name: c.name || String(c), id: c.id || c.name || String(c) }
  );
}

export async function addCompetitor(name: string): Promise<void> {
  await apiFetch("/api/competitors", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function removeCompetitor(id: string): Promise<void> {
  await apiFetch(`/api/competitors/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ── Analyze ────────────────────────────────────────

export async function startAnalysis(req: AnalyzeRequest): Promise<void> {
  await apiFetch("/api/analyze", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ── Reports ────────────────────────────────────────

export async function fetchReports(): Promise<Report[]> {
  const data = await apiFetch<Report[]>("/api/reports");
  return Array.isArray(data) ? data : [];
}

export async function fetchReportDetail(
  id: string | number
): Promise<ReportDetail> {
  return apiFetch<ReportDetail>(`/api/reports/${id}`);
}
