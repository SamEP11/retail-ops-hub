import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { catalogApi } from "../api/endpoints";
import type { ImportReport } from "../api/types";
import { ErrorBox, PageHeader } from "../components/ui";

// Flujo en dos pasos, el estándar en importaciones de empresa:
// 1. Validar (dry run): el backend revisa todo y dice qué cambiaría, sin guardar.
// 2. Confirmar: solo se habilita si la validación no tuvo errores.
export function ImportPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportReport | null>(null);

  const validate = useMutation({
    mutationFn: (f: File) => catalogApi.importFile(f, true),
    onSuccess: setPreview,
  });
  const apply = useMutation({
    mutationFn: (f: File) => catalogApi.importFile(f, false),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });

  async function downloadTemplate() {
    const blob = await catalogApi.template();
    const url = URL.createObjectURL(blob);
    const a = Object.assign(document.createElement("a"), {
      href: url,
      download: "plantilla_catalogo.xlsx",
    });
    a.click();
    URL.revokeObjectURL(url);
  }

  function onFile(f: File | null) {
    setFile(f);
    setPreview(null);
    apply.reset();
    validate.reset();
    if (f) validate.mutate(f);
  }

  const report = apply.data ?? preview;
  const canApply = Boolean(file && preview && preview.errors.length === 0 && !apply.data);

  return (
    <>
      <PageHeader
        title="Importar catálogo"
        actions={
          <button type="button" className="btn-secondary" onClick={() => void downloadTemplate()}>
            Descargar plantilla
          </button>
        }
      />

      <div className="card mb-6 p-4">
        <label htmlFor="file" className="label">
          Archivo .xlsx o .csv (máx. 5 MB, 5.000 filas)
        </label>
        <input
          id="file"
          type="file"
          accept=".xlsx,.csv"
          className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:font-medium file:text-brand-700"
          onChange={(e) => onFile(e.target.files?.[0] ?? null)}
        />
        <p className="mt-2 text-xs text-stone-500">
          Una fila por SKU. Primero se valida todo el archivo; nada se guarda hasta que confirmes.
        </p>
      </div>

      {validate.isPending && <p className="text-sm text-stone-500">Validando…</p>}
      {validate.isError && <ErrorBox error={validate.error} />}
      {apply.isError && <ErrorBox error={apply.error} />}

      {report && (
        <section className="card p-4" aria-label="Resultado">
          <h2 className="mb-3 font-semibold">
            {report.applied
              ? "Importación aplicada"
              : report.errors.length
                ? `${report.errors.length} error${report.errors.length === 1 ? "" : "es"}: corrige el archivo y vuelve a subirlo`
                : "Validación correcta: esto es lo que cambiará"}
          </h2>

          <dl className="mb-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
            {[
              ["Filas", report.rows],
              ["Productos nuevos", report.products_created],
              ["Productos actualizados", report.products_updated],
              ["Variantes nuevas", report.variants_created],
              ["Variantes actualizadas", report.variants_updated],
              ["Precios cambiados", report.prices_set],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-stone-50 p-3">
                <dt className="text-stone-500">{label}</dt>
                <dd className="text-lg font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>

          {report.errors.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-stone-200 text-xs uppercase text-stone-500">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Fila</th>
                    <th className="py-2 pr-4 font-medium">Columna</th>
                    <th className="py-2 font-medium">Problema</th>
                  </tr>
                </thead>
                <tbody>
                  {report.errors.map((e, i) => (
                    <tr key={i} className="border-b border-stone-100 last:border-0">
                      <td className="py-2 pr-4 tabular-nums">{e.row}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{e.column ?? "—"}</td>
                      <td className="py-2 text-red-700">{e.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {canApply && (
            <button
              type="button"
              className="btn-primary"
              disabled={apply.isPending}
              onClick={() => file && apply.mutate(file)}
            >
              {apply.isPending ? "Aplicando…" : "Confirmar importación"}
            </button>
          )}
        </section>
      )}
    </>
  );
}
