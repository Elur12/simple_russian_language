export type Severity = "green" | "orange" | "red";

export interface ViolationDetail {
  rule_id: string;
  rule_name: string;
  severity: Severity;
  problematic_text: string;
  comment: string;
  suggested_rewrite: string;
}

export interface SentenceFinding {
  sentence_index: number;
  severity: Severity;
  violations: ViolationDetail[];
  comment: string;
  suggested_rewrite: string;
}

export interface ParagraphFinding {
  unit_index: number;
  unit_type: "paragraph";
  source_text: string;
  severity: Severity;
  violations: ViolationDetail[];
  overall_comment: string;
  paragraph_rewrite: string;
  sentence_findings: SentenceFinding[];
}

export interface AnalysisResponse {
  summary: {
    green: number;
    orange: number;
    red: number;
    overall: Severity;
  };
  items: ParagraphFinding[];
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface TokenStatus {
  has_token: boolean;
  masked_token?: string;
  updated_at?: string;
}

function authHeader(accessToken: string): Record<string, string> {
  return { Authorization: `Bearer ${accessToken}` };
}

export async function registerUser(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<void> {
  const response = await fetch(`${API_BASE}/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось зарегистрироваться");
  }
}

export async function loginUser(payload: {
  username: string;
  password: string;
}): Promise<AuthTokens> {
  const response = await fetch(`${API_BASE}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Неверный логин или пароль");
  }
  return response.json();
}

export async function getProfileToken(accessToken: string): Promise<TokenStatus> {
  const response = await fetch(`${API_BASE}/profile/token/`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(accessToken),
    },
  });
  if (!response.ok) {
    throw new Error("Не удалось получить статус токена");
  }
  return response.json();
}

export async function saveProfileToken(
  accessToken: string,
  token: string
): Promise<TokenStatus> {
  const response = await fetch(`${API_BASE}/profile/token/`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(accessToken),
    },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось сохранить токен");
  }
  return response.json();
}

export async function deleteProfileToken(accessToken: string): Promise<void> {
  const response = await fetch(`${API_BASE}/profile/token/`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(accessToken),
    },
  });
  if (!response.ok) {
    throw new Error("Не удалось удалить токен");
  }
}

export interface FetchUrlResult {
  title: string;
  text: string;
  url: string;
}

export async function fetchUrlText(url: string, accessToken: string): Promise<FetchUrlResult> {
  const response = await fetch(`${API_BASE}/fetch-url/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(accessToken),
    },
    body: JSON.stringify({ url }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось загрузить страницу");
  }
  return response.json();
}

export async function analyzeText(text: string, accessToken: string): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE}/analyze/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeader(accessToken),
    },
    body: JSON.stringify({ text, include_sentence_findings: true }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || "Не удалось выполнить анализ");
  }

  return response.json();
}
