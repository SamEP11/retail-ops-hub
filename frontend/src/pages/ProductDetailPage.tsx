import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { catalogApi } from "../api/endpoints";
import type { ProductStatus } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { ErrorBox, PageHeader, StatusBadge } from "../components/ui";
import { formatDate, formatMoney, STATUS_LABEL } from "../lib/format";

export function ProductDetailPage() {
  const id = Number(useParams().id);
  const { can } = useAuth();
  const queryClient = useQueryClient();

  const product = useQuery({ queryKey: ["product", id], queryFn: () => catalogApi.product(id) });
  const lists = useQuery({ queryKey: ["price-lists"], queryFn: catalogApi.priceLists });

  const changeStatus = useMutation({
    mutationFn: (status: ProductStatus) => catalogApi.updateProduct(id, { status }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["product", id], updated);
      void queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  if (product.isPending) return <p className="text-sm text-stone-500">Cargando…</p>;
  if (product.isError) return <ErrorBox error={product.error} />;

  const p = product.data;
  const codes = lists.data?.map((l) => l.code) ?? ["B2C", "B2B"];

  return (
    <>
      <Link to="/productos" className="mb-3 inline-block text-sm text-stone-500 hover:underline">
        ← Productos
      </Link>
      <PageHeader
        title={p.name}
        actions={
          can("catalog:write") && (
            <label className="flex items-center gap-2 text-sm">
              Estado
              <select
                className="input w-auto"
                value={p.status}
                disabled={changeStatus.isPending}
                onChange={(e) => changeStatus.mutate(e.target.value as ProductStatus)}
              >
                {(Object.keys(STATUS_LABEL) as ProductStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </option>
                ))}
              </select>
            </label>
          )
        }
      />
      {changeStatus.isError && (
        <div className="mb-4">
          <ErrorBox error={changeStatus.error} />
        </div>
      )}

      <dl className="card mb-6 grid gap-4 p-4 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-stone-500">Estilo</dt>
          <dd className="font-medium">{p.style_code}</dd>
        </div>
        <div>
          <dt className="text-stone-500">Marca</dt>
          <dd className="font-medium">{p.brand}</dd>
        </div>
        <div>
          <dt className="text-stone-500">Categoría</dt>
          <dd className="font-medium">{p.category?.name ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-stone-500">Estado</dt>
          <dd>
            <StatusBadge status={p.status} />
          </dd>
        </div>
        {p.description && (
          <div className="sm:col-span-4">
            <dt className="text-stone-500">Descripción</dt>
            <dd>{p.description}</dd>
          </div>
        )}
      </dl>

      <h2 className="mb-3 font-semibold">Variantes ({p.variants.length})</h2>
      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-stone-200 text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-3 font-medium">SKU</th>
              <th className="px-4 py-3 font-medium">Talla</th>
              <th className="px-4 py-3 font-medium">Color</th>
              <th className="px-4 py-3 font-medium">Código de barras</th>
              {codes.map((c) => (
                <th key={c} className="px-4 py-3 text-right font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {p.variants.map((v) => (
              <tr
                key={v.id}
                className={`border-b border-stone-100 last:border-0 ${v.is_active ? "" : "text-stone-400"}`}
              >
                <td className="px-4 py-3 font-mono text-xs">{v.sku}</td>
                <td className="px-4 py-3">{v.size}</td>
                <td className="px-4 py-3">{v.color}</td>
                <td className="px-4 py-3 font-mono text-xs">{v.barcode ?? "—"}</td>
                {codes.map((c) => (
                  <td key={c} className="px-4 py-3 text-right tabular-nums">
                    {formatMoney(v.prices[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-stone-500">Actualizado {formatDate(p.updated_at)}</p>
    </>
  );
}
