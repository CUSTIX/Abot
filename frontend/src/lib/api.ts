/* Tiny API client. Same origin, session cookie, CSRF token fetched once and kept in memory
   (the CSRF cookie is HttpOnly, so the server hands the token over in /api/auth/csrf/). */

export class ApiError extends Error {
  status: number;
  fields: Record<string, string[]>;

  constructor(status: number, body: unknown) {
    const fields = normalise(body);
    super(firstMessage(fields) ?? `Request failed (${status})`);
    this.status = status;
    this.fields = fields;
  }
}

function normalise(body: unknown): Record<string, string[]> {
  if (!body || typeof body !== "object") return {};
  const out: Record<string, string[]> = {};
  for (const [key, value] of Object.entries(body as Record<string, unknown>)) {
    if (Array.isArray(value)) out[key] = value.map(String);
    else if (typeof value === "string") out[key] = [value];
    else if (value && typeof value === "object") out[key] = Object.values(value).flat().map(String);
  }
  return out;
}

function firstMessage(fields: Record<string, string[]>): string | undefined {
  const entries = Object.entries(fields);
  const general = fields.detail?.[0] ?? fields.non_field_errors?.[0];
  if (general) return general;
  const [key, messages] = entries[0] ?? [];
  return key && messages?.[0] ? `${key.replace(/_/g, " ")}: ${messages[0]}` : undefined;
}

let csrfToken: string | null = null;
let demoLogin: { username: string; password: string } | null = null;

export async function refreshCsrf(): Promise<string> {
  const response = await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  const body = (await response.json()) as {
    csrfToken: string;
    demo: { username: string; password: string } | null;
  };
  csrfToken = body.csrfToken;
  demoLogin = body.demo;
  return csrfToken;
}

/** The public demo's login (only sent by the server when DEMO_MODE is on). */
export const getDemoLogin = () => demoLogin;

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function api<T>(path: string, method: Method = "GET", body?: unknown): Promise<T> {
  const send = async (token: string | null) =>
    fetch(`/api/${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(method !== "GET" && token ? { "X-CSRFToken": token } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  if (method !== "GET" && !csrfToken) await refreshCsrf();
  let response = await send(csrfToken);
  // Logging in or out rotates the token: fetch a fresh one and retry once.
  if (response.status === 403 && method !== "GET") {
    const text = await response.clone().text();
    if (text.includes("CSRF")) response = await send(await refreshCsrf());
  }
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}
