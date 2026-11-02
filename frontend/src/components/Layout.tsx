import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/useAuth";

const ROLE_LABEL = {
  admin: "Administrador",
  comercial: "Comercial",
  bodega: "Bodega",
  analista: "Analista",
} as const;

export function Layout() {
  const { user, can, logout } = useAuth();
  const links = [
    { to: "/productos", label: "Productos", show: can("catalog:read") },
    { to: "/importar", label: "Importar catálogo", show: can("catalog:write") },
  ];

  return (
    <div className="min-h-screen md:grid md:grid-cols-[220px_1fr]">
      <aside className="border-b border-stone-200 bg-white md:min-h-screen md:border-r md:border-b-0">
        <div className="flex items-center gap-2 px-5 py-4">
          <span className="grid size-8 place-items-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            R
          </span>
          <span className="font-semibold">Retail Ops Hub</span>
        </div>
        <nav className="flex gap-1 px-3 pb-3 md:flex-col" aria-label="Principal">
          {links
            .filter((l) => l.show)
            .map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `rounded-lg px-3 py-2 text-sm ${
                    isActive
                      ? "bg-brand-50 font-medium text-brand-700"
                      : "text-stone-600 hover:bg-stone-100"
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
        </nav>
      </aside>

      <div className="min-w-0">
        <header className="flex items-center justify-end gap-4 border-b border-stone-200 bg-white px-4 py-3 md:px-8">
          <div className="text-right text-sm leading-tight">
            <div className="font-medium">{user?.full_name}</div>
            <div className="text-stone-500">{user && ROLE_LABEL[user.role]}</div>
          </div>
          <button type="button" className="btn-secondary" onClick={logout}>
            Salir
          </button>
        </header>
        <main className="px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
