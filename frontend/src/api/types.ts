// Tipos que reflejan los schemas de la API (backend/app/schemas). Si cambia el contrato
// en el backend, se cambia aquí y TypeScript señala cada lugar afectado.

export type Role = "admin" | "comercial" | "bodega" | "analista";
export type ProductStatus = "draft" | "active" | "archived";

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  permissions: string[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
}

// El dinero llega como string ("129900.00") para no perder precisión con floats.
export type Money = string;

export interface ProductSummary {
  id: number;
  style_code: string;
  name: string;
  brand: string;
  status: ProductStatus;
  category: Category | null;
  variant_count: number;
  min_price: Money | null;
  image: string | null;
  updated_at: string;
}

export interface Variant {
  id: number;
  sku: string;
  size: string;
  color: string;
  barcode: string | null;
  is_active: boolean;
  prices: Record<string, Money>;
}

export interface Product {
  id: number;
  style_code: string;
  name: string;
  brand: string;
  description: string;
  status: ProductStatus;
  category: Category | null;
  images: string[];
  variants: Variant[];
  created_at: string;
  updated_at: string;
}

export interface PriceList {
  id: number;
  code: string;
  name: string;
  channel: "b2c" | "b2b";
  currency: string;
}

export interface ImportIssue {
  row: number;
  column: string | null;
  message: string;
}

export interface ImportReport {
  dry_run: boolean;
  applied: boolean;
  rows: number;
  products_created: number;
  products_updated: number;
  variants_created: number;
  variants_updated: number;
  prices_set: number;
  errors: ImportIssue[];
}
