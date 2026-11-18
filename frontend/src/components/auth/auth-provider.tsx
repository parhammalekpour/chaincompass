"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  apiRequest,
  type AuthResponse,
  clearAccessToken,
  fetchAuthResponse,
  logoutRequest,
  refreshSession,
  setAccessToken,
  subscribeToSessionInvalidation,
  type AuthUser,
} from "@/lib/api/client";

export type AuthStatus = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    locale: "en" | "fa",
  ) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const LOGOUT_EVENT = "chaincompass:logout";
const LOGOUT_STORAGE_KEY = "chaincompass:logout-event";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  const loadUser = useCallback(async (auth: AuthResponse) => {
    setAccessToken(auth.access_token);
    return apiRequest<AuthUser>("/api/v1/auth/me");
  }, []);

  const becomeAnonymous = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setStatus("anonymous");
  }, []);

  useEffect(() => {
    let active = true;
    const unsubscribe = subscribeToSessionInvalidation(() => {
      if (active) {
        setUser(null);
        setStatus("anonymous");
      }
    });

    void refreshSession()
      .then(async (auth) => {
        if (!active) return;
        if (auth) {
          const currentUser = await loadUser(auth);
          if (!active) return;
          setUser(currentUser);
          setStatus("authenticated");
        } else {
          setUser(null);
          setStatus("anonymous");
        }
      })
      .catch(() => {
        if (active) {
          setUser(null);
          setStatus("anonymous");
        }
      });

    const onLogout = () => becomeAnonymous();
    let channel: BroadcastChannel | null = null;
    if (typeof BroadcastChannel !== "undefined") {
      try {
        channel = new BroadcastChannel(LOGOUT_EVENT);
        channel.addEventListener("message", onLogout);
      } catch {
        channel = null;
      }
    }

    const onStorage = (event: StorageEvent) => {
      if (event.key === LOGOUT_STORAGE_KEY) onLogout();
    };
    window.addEventListener("storage", onStorage);

    return () => {
      active = false;
      unsubscribe();
      channel?.removeEventListener("message", onLogout);
      channel?.close();
      window.removeEventListener("storage", onStorage);
    };
  }, [becomeAnonymous, loadUser]);

  const login = useCallback(async (email: string, password: string) => {
    const auth = await fetchAuthResponse("/api/v1/auth/login", {
      email,
      password,
    });
    setUser(await loadUser(auth));
    setStatus("authenticated");
  }, [loadUser]);

  const register = useCallback(
    async (email: string, password: string, locale: "en" | "fa") => {
      await apiRequest("/api/v1/auth/register", {
        method: "POST",
        body: { email, password, locale },
        authRetry: false,
      });
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      becomeAnonymous();
      if (typeof BroadcastChannel !== "undefined") {
        try {
          const channel = new BroadcastChannel(LOGOUT_EVENT);
          channel.postMessage({ type: "logout" });
          channel.close();
        } catch {
          try {
            localStorage.setItem(LOGOUT_STORAGE_KEY, String(Date.now()));
          } catch {
            // Cross-tab notification is best-effort when browser storage is blocked.
          }
        }
      } else {
        try {
          localStorage.setItem(LOGOUT_STORAGE_KEY, String(Date.now()));
        } catch {
          // Cross-tab notification is best-effort when browser storage is blocked.
        }
      }
    }
  }, [becomeAnonymous]);

  const value = useMemo(
    () => ({ status, user, login, register, logout }),
    [status, user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
