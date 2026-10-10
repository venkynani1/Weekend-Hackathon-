import type { DashboardPayload, EmployeeRisk, InterventionPayload, InterventionResponse, IngestionRun } from "../types";
import { supabase } from "./supabase";

const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

async function accessToken(): Promise<string> {
  if (!supabase) throw new Error("Supabase is not configured.");
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) throw new Error("Your session has expired. Please sign in again.");
  return data.session.access_token;
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(payload.error ?? `Request failed with status ${response.status}`);
  }
  return response;
}

export async function fetchDashboard(): Promise<DashboardPayload> {
  const response = await apiFetch("/api/dashboard");
  return response.json() as Promise<DashboardPayload>;
}

export async function fetchEmployee(employeeNumber: number): Promise<EmployeeRisk> {
  const response = await apiFetch(`/api/employees/${employeeNumber}`);
  return response.json() as Promise<EmployeeRisk>;
}

export async function fetchIntervention(employeeNumber: number): Promise<InterventionResponse> {
  const response = await apiFetch(`/api/interventions?employee_number=${employeeNumber}`);
  return response.json() as Promise<InterventionResponse>;
}

export async function createIntervention(payload: InterventionPayload): Promise<InterventionResponse["case"]> {
  const response = await apiFetch("/api/interventions", { method: "POST", body: JSON.stringify(payload) });
  return response.json() as Promise<InterventionResponse["case"]>;
}

export async function updateIntervention(caseId: string, payload: Partial<InterventionPayload>): Promise<InterventionResponse["case"]> {
  const response = await apiFetch(`/api/interventions/${caseId}`, { method: "PATCH", body: JSON.stringify(payload) });
  return response.json() as Promise<InterventionResponse["case"]>;
}

export async function fetchIngestionRuns(): Promise<IngestionRun[]> {
  const response = await apiFetch("/api/ingestion-runs?limit=10");
  return response.json() as Promise<IngestionRun[]>;
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const response = await apiFetch(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
