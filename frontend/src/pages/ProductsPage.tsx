import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { catalogApi } from "../api/endpoints";
import type { ProductStatus } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { ErrorBox, PageHeader, StatusBadge } from "../components/ui";
import { formatDate, formatMoney } from "../lib/format";

const PAGE_SIZE = 20;

export function ProductsPage() {
  const { can } = useAuth();
  // Los filtros viven en la URL: se pueden compartir y sobreviven a un F5.
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const status = (params.get("status") ?? "") as ProductStatus | "";
  const categoryId = params.get("categoria") ?? "";
  const priceList = params.get("lista") ?? "B2C";
  const page = Math.max(1, Number(params.get("pagina") ?? 1));

  const [search, setSearch] = useState(q);
  // Debounce: espera 300 ms tras la última tecla antes de consultar la API.
  useEffect(() => {
    const id = setTimeout(() => {
      if (search !== q) update({ q: search, pagina: "" });
    }, 300);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  function update(next: Record<string, string>) {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(next)) {
      if (v) p.set(k, v);
      else p.delete(k);
    }
    setParams(p, { replace: true });
  }

  const categories = useQuery({ queryKey: ["categories"], queryFn: catalogApi.categories });
  const lists = useQuery({ queryKey: ["price-lists"], queryFn: catalogApi.priceLists });
  const products = useQuery({
    queryKey: ["products", { q, status, categoryId, priceList, page }],
    queryFn: () =>
      catalogApi.products({
        q,
        status,
        category_id: categoryId ? Number(categoryId) : "",
        price_list: priceList,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData, // la tabla no parpadea al cambiar de página
  });

  const total = products.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <PageHeader
        title="Productos"
        actions={
          can("catalog:write") && (
            <Link to="/importar" className="btn-primary">
              Importar catálogo
            </Link>
          )
        }
      />

      <div className="card mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_1fr]">
        <input
          type="search"
          aria-label="Buscar"
          placeholder="Buscar por nombre, estilo, marca o SKU"
          className="input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          aria-label="Estado"
          className="input"
          value={status}
          onChange={(e) => update({ status: e.target.value, pagina: "" })}
        >
          <option value="">Todos los estados</option>
          <option value="active">Activos</option>
          <option value="draft">Borradores</option>
          <option value="archived">Archivados</option>
        </select>
        <select
          aria-label="Categoría"
          className="input"
          value={categoryId}
          onChange={(e) => update({ categoria: e.target.value, pagina: "" })}
        >
          <option value="">Todas las categorías</option>
          {categories.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Lista de precio"
          className="input"
          value={priceList}
          onChange={(e) => update({ lista: e.target.value === "B2C" ? "" : e.target.value })}
        >
          {(lists.data ?? [{ id: 0, code: "B2C", name: "Precio al público" }]).map((l) => (
            <option key={l.code} value={l.code}>
              {l.name} ({l.code})
            </option>
          ))}
        </select>
      </div>

      {products.isError && <ErrorBox error={products.error} />}

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3 font-medium">Producto</th>
              <th className="px-4 py-3 font-medium">Categoría</th>
              <th className="px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3 text-right font-medium">Variantes</th>
              <th className="px-4 py-3 text-right font-medium">Desde</th>
              <th className="px-4 py-3 font-medium">Actualizado</th>
            </tr>
          </thead>
          <tbody className={products.isPlaceholderData ? "opacity-60" : ""}>
            {products.data?.items.map((p) => (
              <tr key={p.id} className="border-b border-stone-100 last:border-0 hover:bg-stone-50">
                <td className="px-4 py-3">
                  <Link to={`/productos/${p.id}`} className="font-medium text-brand-700 hover:underline">
                    {p.name}
                  </Link>
                  <div className="text-xs text-stone-500">
                    {p.style_code} · {p.brand}
                  </div>
                </td>
                <td className="px-4 py-3 text-stone-600">{p.category?.name ?? "—"}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={p.status} />
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{p.variant_count}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatMoney(p.min_price)}</td>
                <td className="px-4 py-3 text-stone-500">{formatDate(p.updated_at)}</td>
              </tr>
            ))}
            {products.isSuccess && products.data.items.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-stone-500">
                  No hay productos con esos filtros.
                </td>
              </tr>
            )}
            {products.isPending && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-stone-500">
                  Cargando…
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <nav className="mt-4 flex items-center justify-between text-sm" aria-label="Paginación">
        <span className="text-stone-500">
          {total} producto{total === 1 ? "" : "s"}
        </span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={page <= 1}
            onClick={() => update({ pagina: String(page - 1) })}
          >
            Anterior
          </button>
          <span className="tabular-nums">
            {page} / {pages}
          </span>
          <button
            type="button"
            className="btn-secondary"
            disabled={page >= pages}
            onClick={() => update({ pagina: String(page + 1) })}
          >
            Siguiente
          </button>
        </div>
      </nav>
    </>
  );
}
