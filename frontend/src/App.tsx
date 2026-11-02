import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/useAuth";
import { Layout } from "./components/Layout";
import { ImportPage } from "./pages/ImportPage";
import { LoginPage } from "./pages/LoginPage";
import { ProductDetailPage } from "./pages/ProductDetailPage";
import { ProductsPage } from "./pages/ProductsPage";

export default function App() {
  const { user, loading, can } = useAuth();

  if (loading) {
    return <p className="p-8 text-sm text-stone-500">Cargando…</p>;
  }
  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/productos" element={<ProductsPage />} />
        <Route path="/productos/:id" element={<ProductDetailPage />} />
        {can("catalog:write") && <Route path="/importar" element={<ImportPage />} />}
        <Route path="*" element={<Navigate to="/productos" replace />} />
      </Route>
    </Routes>
  );
}
