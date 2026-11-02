import { api, toQuery } from "./client";
import type {
  Category,
  ImportReport,
  Me,
  Page,
  PriceList,
  Product,
  ProductStatus,
  ProductSummary,
} from "./types";

export const authApi = {
  login: (email: string, password: string) =>
    api<{ access_token: string; expires_in: number }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  me: () => api<Me>("/auth/me"),
};

export interface ProductFilters {
  q?: string;
  status?: ProductStatus | "";
  category_id?: number | "";
  price_list?: string;
  limit?: number;
  offset?: number;
}

export const catalogApi = {
  products: (f: ProductFilters) => api<Page<ProductSummary>>(`/products${toQuery({ ...f })}`),
  product: (id: number) => api<Product>(`/products/${id}`),
  updateProduct: (id: number, data: Partial<Pick<Product, "status" | "name" | "description">>) =>
    api<Product>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  categories: () => api<Category[]>("/categories"),
  priceLists: () => api<PriceList[]>("/price-lists"),
  importFile: (file: File, dryRun: boolean) => {
    const form = new FormData();
    form.append("file", file);
    return api<ImportReport>(`/catalog/import${toQuery({ dry_run: String(dryRun) })}`, {
      method: "POST",
      body: form,
    });
  },
  template: () => api<Blob>("/catalog/import/template"),
};
