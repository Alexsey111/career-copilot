"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { api } from "@/lib/api";

interface User {
  id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshTokens = useCallback(async () => {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return false;
    try {
      const res = await api.refreshToken(refreshToken);
      localStorage.setItem("auth_token", res.access_token);
      localStorage.setItem("refresh_token", res.refresh_token);
      setToken(res.access_token);
      return true;
    } catch {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("refresh_token");
      setToken(null);
      setUser(null);
      return false;
    }
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem("auth_token");
    if (saved) {
      setToken(saved);
      api
        .getMe(saved)
        .then(setUser)
        .catch(async () => {
          const refreshed = await refreshTokens();
          if (refreshed) {
            const newToken = localStorage.getItem("auth_token");
            if (newToken) {
              try {
                const me = await api.getMe(newToken);
                setUser(me);
              } catch {
                localStorage.removeItem("auth_token");
                localStorage.removeItem("refresh_token");
                setToken(null);
              }
            }
          }
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [refreshTokens]);

  const login = async (email: string, password: string) => {
    const res = await api.login(email, password);
    localStorage.setItem("auth_token", res.access_token);
    localStorage.setItem("refresh_token", res.refresh_token);
    setToken(res.access_token);
    const me = await api.getMe(res.access_token);
    setUser(me);
  };

  const register = async (email: string, password: string) => {
    const res = await api.register(email, password);
    localStorage.setItem("auth_token", res.access_token);
    localStorage.setItem("refresh_token", res.refresh_token);
    setToken(res.access_token);
    const me = await api.getMe(res.access_token);
    setUser(me);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("refresh_token");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
