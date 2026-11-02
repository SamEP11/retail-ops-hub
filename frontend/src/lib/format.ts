import type { Money, ProductStatus } from "../api/types";

const cop = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

/** "129900.00" -> "$ 129.900". Vacío si no hay precio. */
export function formatMoney(value: Money | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return Number.isFinite(n) ? cop.format(n) : "—";
}

const dateFmt = new Intl.DateTimeFormat("es-CO", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string): string {
  return dateFmt.format(new Date(iso));
}

export const STATUS_LABEL: Record<ProductStatus, string> = {
  draft: "Borrador",
  active: "Activo",
  archived: "Archivado",
};
