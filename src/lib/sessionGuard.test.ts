import { afterEach, describe, expect, it, vi } from "vitest";
import { reloadIfSessionExpired, sessionExpired } from "./sessionGuard";

const reload = vi.fn();
const store = new Map<string, string>();
vi.stubGlobal("sessionStorage", {
  getItem: (k: string) => store.get(k) ?? null,
  setItem: (k: string, v: string) => void store.set(k, v),
  clear: () => store.clear(),
});

function mockFetch(res: Partial<Response> | Error) {
  vi.stubGlobal("fetch", vi.fn(() => (res instanceof Error ? Promise.reject(res) : Promise.resolve(res as Response))));
}

afterEach(() => {
  reload.mockReset();
  store.clear();
});

describe("sessionGuard", () => {
  it("una redirección de /health es sesión caducada", async () => {
    mockFetch({ type: "opaqueredirect", status: 0 });
    expect(await sessionExpired()).toBe(true);
  });

  it("sin red de verdad no es sesión caducada", async () => {
    mockFetch(new TypeError("Failed to fetch"));
    expect(await sessionExpired()).toBe(false);
    mockFetch({ type: "basic", status: 200 });
    expect(await sessionExpired()).toBe(false);
  });

  it("recarga una vez y no entra en bucle", async () => {
    vi.stubGlobal("window", { location: { reload } });
    mockFetch({ type: "opaqueredirect", status: 0 });
    expect(await reloadIfSessionExpired()).toBe(true);
    expect(await reloadIfSessionExpired()).toBe(false);
    expect(reload).toHaveBeenCalledTimes(1);
  });
});
