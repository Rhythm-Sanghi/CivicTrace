const API_BASE = "http://localhost:8000/api/v1";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: "CITIZEN" | "REVIEWER" | "OPERATOR" | "ADMINISTRATOR";
  department_id?: string;
}

export interface Category {
  id: string;
  name: string;
  code: string;
  description: string;
  default_severity_weight: number;
}

export interface Case {
  id: string;
  public_id: string;
  category_id: string;
  category?: Category;
  title: string;
  description: string;
  latitude: number;
  longitude: number;
  address_reference?: string;
  state: "SUBMITTED" | "UNDER_REVIEW" | "VERIFIED" | "ASSIGNED" | "IN_PROGRESS" | "RESOLUTION_CLAIMED" | "AWAITING_VERIFICATION" | "RESOLVED" | "DISPUTED" | "REOPENED" | "REJECTED";
  priority_score: number;
  priority_band: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  priority_breakdown?: string;
  created_at: string;
  updated_at: string;
  verified_at?: string;
  resolved_at?: string;
  report_count: number;
}

export interface CaseEvent {
  id: string;
  case_id: string;
  event_index: number;
  event_type: string;
  public_actor_label: string;
  payload_json: string;
  schema_version: number;
  previous_event_hash: string;
  current_event_hash: string;
  created_at: string;
}

export interface Report {
  id: string;
  public_id: string;
  category_id: string;
  category?: Category;
  title: string;
  description: string;
  latitude: number;
  longitude: number;
  address_reference?: string;
  moderation_status: string;
  case_id?: string;
  guest_pseudonym?: string;
  created_at: string;
}

export interface DuplicateCandidate {
  id: string;
  report_id: string;
  target_case_id: string;
  distance_meters: number;
  spatial_score: number;
  text_score: number;
  category_score: number;
  temporal_score: number;
  composite_score: number;
  explanation: string;
  status: string;
  created_at: string;
  target_case?: Case;
}

export interface NeighborhoodStats {
  service_area: string;
  open_cases: number;
  verified_resolutions: number;
  disputed_resolutions: number;
  awaiting_verification: number;
  total_reports: number;
  median_resolution_days: number;
  category_counts: Record<string, number>;
  priority_counts: Record<string, number>;
}

export function getAuthToken(): string | null {
  return localStorage.getItem("civictrace_token");
}

export function setAuthToken(token: string) {
  localStorage.setItem("civictrace_token", token);
}

export function clearAuthToken() {
  localStorage.removeItem("civictrace_token");
  localStorage.removeItem("civictrace_user");
}

export function getCurrentUser(): User | null {
  const u = localStorage.getItem("civictrace_user");
  return u ? JSON.parse(u) : null;
}

export function setCurrentUser(user: User) {
  localStorage.setItem("civictrace_user", JSON.stringify(user));
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(errorBody.detail || "Request failed");
  }

  return res.json();
}

export const api = {
  // Categories
  getCategories: () => request<Category[]>("/reports/categories"),

  // Reports
  submitReport: (data: {
    category_id: string;
    title: string;
    description: string;
    latitude: number;
    longitude: number;
    address_reference?: string;
    guest_pseudonym?: string;
  }) => request<Report>("/reports", { method: "POST", body: JSON.stringify(data) }),

  getReports: () => request<Report[]>("/reports"),
  getMyReports: () => request<Report[]>("/reports/my"),
  moderateReport: (reportId: string, decision: "APPROVED" | "FLAGGED" | "REJECTED", notes?: string) =>
    request<Report>(`/reports/${reportId}/moderate`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    }),

  uploadEvidence: async (reportId: string, file: File, caption?: string) => {
    const token = getAuthToken();
    const formData = new FormData();
    formData.append("file", file);
    if (caption) formData.append("caption", caption);

    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}/reports/${reportId}/evidence`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail);
    }
    return res.json();
  },

  // Duplicates
  getPendingDuplicates: () => request<DuplicateCandidate[]>("/reports/duplicates/pending"),
  decideDuplicate: (candidateId: string, decision: "APPROVE" | "REJECT", notes?: string) =>
    request<DuplicateCandidate>(`/reports/duplicates/${candidateId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, notes }),
    }),

  // Cases
  getCases: (params?: { category_id?: string; priority_band?: string; state?: string }) => {
    const query = new URLSearchParams();
    if (params?.category_id) query.append("category_id", params.category_id);
    if (params?.priority_band) query.append("priority_band", params.priority_band);
    if (params?.state) query.append("state", params.state);
    return request<Case[]>(`/cases?${query.toString()}`);
  },

  getCase: (caseId: string) => request<Case>(`/cases/${caseId}`),
  getCaseEvents: (caseId: string) => request<CaseEvent[]>(`/cases/${caseId}/events`),
  verifyLedger: (caseId: string) =>
    request<{ case_id: string; is_valid: boolean; total_events: number; error_message?: string; latest_event_hash?: string }>(
      `/cases/${caseId}/events/verify`
    ),

  submitResolutionClaim: (caseId: string, data: { work_summary: string; actions_taken: string }) =>
    request<any>(`/cases/${caseId}/claims`, { method: "POST", body: JSON.stringify(data) }),

  submitVerification: (caseId: string, data: { outcome: string; notes: string; guest_pseudonym?: string }) =>
    request<any>(`/cases/${caseId}/verifications`, { method: "POST", body: JSON.stringify(data) }),

  transitionCase: (caseId: string, target_state: string, notes?: string) =>
    request<Case>(`/cases/${caseId}/transition?target_state=${target_state}&notes=${encodeURIComponent(notes || "")}`, {
      method: "POST",
    }),

  getNeighborhoodStats: () => request<NeighborhoodStats>("/cases/neighborhood/stats"),

  // Auth
  login: async (email: string, pass: string) => {
    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", pass);
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData.toString(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Login failed" }));
      throw new Error(err.detail);
    }
    const data = await res.json();
    setAuthToken(data.access_token);
    setCurrentUser(data.user);
    return data;
  },

  register: (data: { email: string; password: string; display_name: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  getMe: () => request<User>("/auth/me"),
};
