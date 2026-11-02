import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { setUnauthorizedHandler, tokenStore } from "../api/client";
import { authApi } from "../api/endpoints";
import type { Me } from "../api/types";

export interface AuthState {
  user: Me | null;
  loading: boolean;
  can: (permission: string) => boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState(tokenStore.get);

  const logout = useCallback(() => {
    tokenStore.set(null);
    setToken(null);
    queryClient.clear();
  }, [queryClient]);

  // Si el backend responde 401 (token vencido o usuario desactivado), cerramos sesión.
  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  const me = useQuery({
    queryKey: ["me", token],
    queryFn: authApi.me,
    enabled: Boolean(token),
    retry: false,
    staleTime: 5 * 60_000,
  });

  const login = useCallback(async (email: string, password: string) => {
    const { access_token } = await authApi.login(email, password);
    tokenStore.set(access_token);
    setToken(access_token);
  }, []);

  const value = useMemo<AuthState>(() => {
    const user = token ? (me.data ?? null) : null;
    return {
      user,
      loading: Boolean(token) && me.isPending,
      // Solo para mostrar u ocultar botones: la seguridad real la aplica el backend.
      can: (permission) => Boolean(user?.permissions.includes(permission)),
      login,
      logout,
    };
  }, [token, me.data, me.isPending, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
