import type { ReactNode } from "react";

import { ApiError } from "../api/client";
import type { ProductStatus } from "../api/types";
import { STATUS_LABEL } from "../lib/format";

const STATUS_STYLE: Record<ProductStatus, string> = {
  active: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  draft: "bg-amber-50 text-amber-700 ring-amber-600/20",
  archived: "bg-stone-100 text-stone-600 ring-stone-500/20",
};

export function StatusBadge({ status }: { status: ProductStatus }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_STYLE[status]}`}
    >
      {STATUS_LABEL[status]}
    </span>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : "Error inesperado";
  const requestId = error instanceof ApiError ? error.requestId : null;
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      {message}
      {requestId && (
        <span className="mt-1 block text-xs text-red-600">
          Código para soporte: <code>{requestId}</code>
        </span>
      )}
    </div>
  );
}

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <h1 className="text-xl font-semibold">{title}</h1>
      {actions}
    </div>
  );
}
