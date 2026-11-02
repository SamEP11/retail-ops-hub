import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "./App";
import { ME_COMERCIAL, mockApi, renderApp, reply } from "./test/utils";

const PRODUCTS = {
  items: [
    {
      id: 1, style_code: "CAM-OXF", name: "Camisa Oxford", brand: "Retail Ops", status: "active",
      category: { id: 1, name: "Camisas", slug: "camisas" }, variant_count: 8,
      min_price: "129900.00", image: null, updated_at: "2026-11-01T10:00:00Z",
    },
  ],
  total: 1, limit: 20, offset: 0,
};
const CATALOG_ROUTES = {
  "GET /products": PRODUCTS,
  "GET /categories": [{ id: 1, name: "Camisas", slug: "camisas" }],
  "GET /price-lists": [
    { id: 1, code: "B2C", name: "Precio al público", channel: "b2c", currency: "COP" },
    { id: 2, code: "B2B", name: "Precio mayorista", channel: "b2b", currency: "COP" },
  ],
};

describe("login", () => {
  it("sin sesión muestra el login y al ingresar va a productos", async () => {
    mockApi({
      "POST /auth/login": { access_token: "nuevo", expires_in: 1800 },
      "GET /auth/me": ME_COMERCIAL,
      ...CATALOG_ROUTES,
    });
    renderApp(<App />, { token: null });

    await userEvent.type(screen.getByLabelText("Email"), "comercial@retailops.dev");
    await userEvent.type(screen.getByLabelText("Contraseña"), "Demo12345!");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));

    expect(await screen.findByRole("heading", { name: "Productos" })).toBeInTheDocument();
    expect(localStorage.getItem("roh.token")).toBe("nuevo");
  });

  it("muestra el error de la API si las credenciales fallan", async () => {
    mockApi({
      "POST /auth/login": reply(401, { detail: "Email o contraseña incorrectos" }),
    });
    renderApp(<App />, { token: null });
    await userEvent.type(screen.getByLabelText("Email"), "x@x.dev");
    await userEvent.type(screen.getByLabelText("Contraseña"), "mala");
    await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email o contraseña incorrectos");
  });

  it("si el token venció (401) vuelve al login", async () => {
    mockApi({ "GET /auth/me": reply(401, { detail: "Credenciales inválidas" }) });
    renderApp(<App />, { token: "vencido" });
    expect(await screen.findByRole("button", { name: "Ingresar" })).toBeInTheDocument();
    expect(localStorage.getItem("roh.token")).toBeNull();
  });
});

describe("productos", () => {
  it("lista productos con precio formateado", async () => {
    mockApi({ "GET /auth/me": ME_COMERCIAL, ...CATALOG_ROUTES });
    renderApp(<App />, { route: "/productos" });

    const row = (await screen.findByRole("link", { name: "Camisa Oxford" })).closest("tr")!;
    expect(within(row).getByText("Activo")).toBeInTheDocument();
    expect(within(row).getByText(/129\.900/)).toBeInTheDocument();
  });

  it("la búsqueda se envía a la API (con debounce)", async () => {
    const calls = mockApi({ "GET /auth/me": ME_COMERCIAL, ...CATALOG_ROUTES });
    renderApp(<App />, { route: "/productos" });
    await screen.findByRole("link", { name: "Camisa Oxford" });

    await userEvent.type(screen.getByLabelText("Buscar"), "oxf");
    await waitFor(() =>
      expect(calls.some((c) => c.url.searchParams.get("q") === "oxf")).toBe(true),
    );
  });

  it("un analista no ve el botón de importar", async () => {
    mockApi({
      "GET /auth/me": { ...ME_COMERCIAL, role: "analista", permissions: ["catalog:read"] },
      ...CATALOG_ROUTES,
    });
    renderApp(<App />, { route: "/productos" });
    await screen.findByRole("link", { name: "Camisa Oxford" });
    expect(screen.queryByText("Importar catálogo")).not.toBeInTheDocument();
  });
});

describe("importación", () => {
  const ok = {
    dry_run: true, applied: false, rows: 2, products_created: 1, products_updated: 0,
    variants_created: 2, variants_updated: 0, prices_set: 4, errors: [],
  };

  it("valida primero y solo permite confirmar si no hay errores", async () => {
    const calls = mockApi({
      "GET /auth/me": ME_COMERCIAL,
      "POST /catalog/import": (url: URL) =>
        url.searchParams.get("dry_run") === "true" ? ok : { ...ok, dry_run: false, applied: true },
    });
    renderApp(<App />, { route: "/importar" });
    const file = new File(["style_code,..."], "catalogo.csv", { type: "text/csv" });
    await userEvent.upload(await screen.findByLabelText(/Archivo/), file);

    expect(await screen.findByText(/Validación correcta/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar importación" }));
    expect(await screen.findByText("Importación aplicada")).toBeInTheDocument();

    const posts = calls.filter((c) => c.method === "POST");
    expect(posts.map((c) => c.url.searchParams.get("dry_run"))).toEqual(["true", "false"]);
  });

  it("muestra los errores por fila y no deja confirmar", async () => {
    mockApi({
      "GET /auth/me": ME_COMERCIAL,
      "POST /catalog/import": {
        ...ok,
        errors: [{ row: 3, column: "price_b2c", message: "'abc' no es un número" }],
      },
    });
    renderApp(<App />, { route: "/importar" });
    await userEvent.upload(
      await screen.findByLabelText(/Archivo/),
      new File(["x"], "c.csv", { type: "text/csv" }),
    );

    expect(await screen.findByText("'abc' no es un número")).toBeInTheDocument();
    expect(screen.getByText(/1 error/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar importación" })).not.toBeInTheDocument();
  });
});
