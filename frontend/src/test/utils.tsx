import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AuthProvider } from "../auth/AuthContext";

class Reply {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {}
}

/** Respuesta con un código distinto de 200: `reply(401, { detail: "..." })`. */
export const reply = (status: number, body: unknown) => new Reply(status, body);

type Route = unknown | Reply | ((url: URL, init: RequestInit) => unknown);

/** Reemplaza fetch. Cada ruta ("GET /products") responde un JSON (200), un `reply(...)` o
 * una función que recibe la URL y devuelve cualquiera de los dos. */
export function mockApi(routes: Record<string, Route>) {
  const calls: { method: string; url: URL; init: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    calls.push({ method, url, init });

    const key = `${method} ${url.pathname.replace("/api/v1", "")}`;
    let result: unknown = key in routes ? routes[key] : reply(404, { detail: `sin mock: ${key}` });
    if (typeof result === "function") result = result(url, init);
    const { status, body } = result instanceof Reply ? result : new Reply(200, result);

    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json", "X-Request-ID": "req-123" },
    });
  });
  return calls;
}

export const ME_COMERCIAL = {
  id: 1,
  email: "comercial@retailops.dev",
  full_name: "Carlos Comercial",
  role: "comercial",
  permissions: ["catalog:read", "catalog:write"],
};

export function renderApp(ui: ReactElement, { route = "/", token = "t" as string | null } = {}) {
  if (token) localStorage.setItem("roh.token", token);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
