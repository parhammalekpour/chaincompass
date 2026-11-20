"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  apiRequest,
  ApiError,
  type AuthResponse,
  clearAccessToken,
  fetchAuthResponse,
  logoutRequest,
  refreshSession,
  setAccessToken,
  subscribeToSessionInvalidation,
  type AuthUser,
} from "@/lib/api/client";

export type AuthStatus = "loading" | "authenticated" | "anonymous" | "error";
export const INITIAL_SESSION_REFRESH_TIMEOUT_MS = 10_000;

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
  retryInitialSession: () => Promise<void>;
  refreshCurrentUser: () => Promise<AuthUser>;
  restoreSession: () => Promise<AuthUser>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const LOGOUT_EVENT = "chaincompass:logout";
const LOGOUT_STORAGE_KEY = "chaincompass:logout-event";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const bootstrapSequence = useRef(0);

  const loadUser = useCallback(async (
    auth: AuthResponse,
    signal?: AbortSignal,
  ) => {
    setAccessToken(auth.access_token);
    return apiRequest<AuthUser>("/api/v1/auth/me", { signal });
  }, []);

  const becomeAnonymous = useCallback(() => {
    clearAccessToken();
    setUser(null);
    setStatus("anonymous");
  }, []);

  const refreshCurrentUser = useCallback(async () => {
    const currentUser = await apiRequest<AuthUser>("/api/v1/auth/me");
    setUser(currentUser);
    setStatus("authenticated");
    return currentUser;
  }, []);

  const restoreSession = useCallback(async () => {
    try {
      const auth = await refreshSession();
      if (!auth) throw new ApiError("invalid_refresh_token", 401);
      const currentUser = await loadUser(auth);
      setUser(currentUser);
      setStatus("authenticated");
      return currentUser;
    } catch (error) {
      becomeAnonymous();
      throw error;
    }
  }, [becomeAnonymous, loadUser]);

  const bootstrapSession = useCallback(async () => {
    const sequence = ++bootstrapSequence.current;
    const controller = new AbortController();
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const timedOut = new Promise<never>((_, reject) => {
      timeout = setTimeout(() => {
        controller.abort();
        reject(new Error("initial_session_timeout"));
      }, INITIAL_SESSION_REFRESH_TIMEOUT_MS);
    });
    const isCurrentAttempt = () => sequence === bootstrapSequence.current;

    try {
      const currentUser = await Promise.race([
        (async () => {
          const auth = await refreshSession(controller.signal);
          if (!auth) return null;
          if (controller.signal.aborted) {
            throw new Error("initial_session_timeout");
          }
          const user = await loadUser(auth, controller.signal);
          if (controller.signal.aborted) {
            throw new Error("initial_session_timeout");
          }
          return user;
        })(),
        timedOut,
      ]);

      if (!isCurrentAttempt()) return;
      if (currentUser) {
        setUser(currentUser);
        setStatus("authenticated");
      } else {
        setUser(null);
        setStatus("anonymous");
      }
    } catch (error) {
      if (!isCurrentAttempt()) return;
      if (error instanceof ApiError && error.status === 401) {
        becomeAnonymous();
      } else {
        clearAccessToken();
        setUser(null);
        setStatus("error");
      }
    } finally {
      if (timeout !== undefined) clearTimeout(timeout);
    }
  }, [becomeAnonymous, loadUser]);

  const retryInitialSession = useCallback(async () => {
    setStatus("loading");
    await bootstrapSession();
  }, [bootstrapSession]);

  useEffect(() => {
    let active = true;
    const unsubscribe = subscribeToSessionInvalidation(() => {
      if (active) {
        setUser(null);
        setStatus("anonymous");
      }
    });

    const isOAuthCallback = /\/(?:en|fa)\/auth\/callback\/?$/.test(
      window.location.pathname,
    );
    if (!isOAuthCallback) {
      // Start async bootstrap; state updates come from its resolved request.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void bootstrapSession();
    }

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
      bootstrapSequence.current += 1;
      unsubscribe();
      channel?.removeEventListener("message", onLogout);
      channel?.close();
      window.removeEventListener("storage", onStorage);
    };
  }, [becomeAnonymous, bootstrapSession]);

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
    () => ({
      status,
      user,
      login,
      register,
      logout,
      retryInitialSession,
      refreshCurrentUser,
      restoreSession,
    }),
    [
      status,
      user,
      login,
      register,
      logout,
      retryInitialSession,
      refreshCurrentUser,
      restoreSession,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
