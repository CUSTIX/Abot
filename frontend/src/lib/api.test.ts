import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("sends the CSRF token on writes and retries once when it was rotated", async () => {
    const calls: { url: string; token: string | null }[] = [];
    let token = "first";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === "/api/auth/csrf/") return json(200, { csrfToken: token, demo: null });
        const headers = (init?.headers ?? {}) as Record<string, string>;
        calls.push({ url, token: headers["X-CSRFToken"] ?? null });
        if (calls.length === 1) {
          token = "second"; // e.g. the user signed in elsewhere: the old token is stale
          return new Response("CSRF Failed: CSRF token missing.", { status: 403 });
        }
        return json(201, { id: 7 });
      }),
    );
    await expect(api("wallets/", "POST", { name: "X" })).resolves.toEqual({ id: 7 });
    expect(calls.map((c) => c.token)).toEqual(["first", "second"]);
  });

  it("turns field errors into a readable message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(400, { amount: ["The amount must be more than zero."] })));
    const error = await api("transactions/").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).fields.amount).toEqual(["The amount must be more than zero."]);
    expect((error as ApiError).message).toBe("amount: The amount must be more than zero.");
  });

  it("prefers the general detail message", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json(400, { detail: "Wrong username or password." })));
    await expect(api("auth/login/")).rejects.toThrow("Wrong username or password.");
  });
});
