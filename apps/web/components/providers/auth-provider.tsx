"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import {
  LoginInput,
  RegisterInput,
  RegisterResponse,
  UserMe,
} from "@/lib/schemas/auth";
import {
  CreateOrganizationInput,
  Organization,
} from "@/lib/schemas/organizations";
import {
  getCurrentUser,
  loginUser,
  logoutUser,
  registerUser,
} from "@/lib/api/auth";
import {
  ACTIVE_ORG_KEY,
  SESSION_EXPIRED_EVENT,
  SESSION_TOKENS_EVENT,
  SessionTokensDetail,
  clearStoredSession,
  hasSessionHint,
  purgeLegacyTokenStorage,
  refreshSession,
  storeSession,
} from "@/lib/api/http";
import {
  createOrganization,
  listOrganizations,
} from "@/lib/api/organizations";

export interface AuthContextType {
  user: UserMe | null;
  token: string | null;
  organizations: Organization[];
  activeOrg: Organization | null;
  activeOrgId: string | null;
  activeRole: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginInput) => Promise<{ user: UserMe; organizations: Organization[] }>;
  register: (data: RegisterInput) => Promise<RegisterResponse>;
  logout: () => Promise<void>;
  createOrg: (data: CreateOrganizationInput) => Promise<Organization>;
  selectOrg: (orgId: string) => void;
  refetchOrganizations: () => Promise<Organization[]>;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize session on mount
  useEffect(() => {
    let isMounted = true;

    function resetSessionState() {
      setUser(null);
      setToken(null);
      setOrganizations([]);
      setActiveOrgId(null);
    }

    async function initSession() {
      try {
        purgeLegacyTokenStorage();
        // Signed-out browsers skip the refresh call; the flag holds no secret.
        if (!hasSessionHint()) return;

        // The access token lives only in memory, so every page load exchanges the HttpOnly refresh
        // cookie for a new one. Shared single-flight refresh: requests that hit a 401 while the
        // page loads join this same call instead of presenting the cookie a second time.
        const outcome = await refreshSession();
        if (!isMounted) return;
        if (outcome.status !== "ok") {
          // "rejected": the API refused the refresh cookie and the session is already cleared.
          // "failed" (offline, aborted by navigation, server error): keep the hint so the next
          // page load can restore the session; only this page renders signed out.
          resetSessionState();
          return;
        }
        const accessToken = outcome.accessToken;
        setToken(accessToken);

        const [me, orgs] = await Promise.all([getCurrentUser(accessToken), listOrganizations(accessToken)]);
        if (!isMounted) return;
        setUser(me);
        setOrganizations(orgs);

        // Restore active org
        const storedOrgId = typeof window !== "undefined" ? localStorage.getItem(ACTIVE_ORG_KEY) : null;
        if (storedOrgId && orgs.some((o) => o.id === storedOrgId)) {
          setActiveOrgId(storedOrgId);
        } else if (orgs.length > 0) {
          setActiveOrgId(orgs[0].id);
          if (typeof window !== "undefined") {
            localStorage.setItem(ACTIVE_ORG_KEY, orgs[0].id);
          }
        }
      } catch {
        // Loading the profile failed (e.g. the request was aborted by navigating away, or the
        // network dropped). Never end the session for that: a rejected refresh cookie is handled
        // by the shared client, which clears it and signs the user out.
        if (isMounted) resetSessionState();
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, []);

  // Keep React state in sync with refreshes done by the shared API client,
  // and sign out when the refresh token is rejected.
  useEffect(() => {
    function handleTokens(event: Event) {
      setToken((event as CustomEvent<SessionTokensDetail>).detail.accessToken);
    }

    function handleExpired() {
      setUser(null);
      setToken(null);
      setOrganizations([]);
      setActiveOrgId(null);
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login?expired=1");
      }
    }

    window.addEventListener(SESSION_TOKENS_EVENT, handleTokens);
    window.addEventListener(SESSION_EXPIRED_EVENT, handleExpired);
    return () => {
      window.removeEventListener(SESSION_TOKENS_EVENT, handleTokens);
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleExpired);
    };
  }, []);

  const login = useCallback(async (credentials: LoginInput) => {
    setIsLoading(true);
    try {
      const tokens = await loginUser(credentials);
      setToken(tokens.access_token);
      storeSession(tokens.access_token);

      const [me, orgs] = await Promise.all([
        getCurrentUser(tokens.access_token),
        listOrganizations(tokens.access_token),
      ]);

      setUser(me);
      setOrganizations(orgs);

      let chosenOrgId: string | null = null;
      if (orgs.length > 0) {
        chosenOrgId = orgs[0].id;
        setActiveOrgId(chosenOrgId);
        if (typeof window !== "undefined") {
          localStorage.setItem(ACTIVE_ORG_KEY, chosenOrgId);
        }
      } else {
        setActiveOrgId(null);
      }

      return { user: me, organizations: orgs };
    } finally {
      setIsLoading(false);
    }
  }, []);

  const register = useCallback(async (data: RegisterInput) => {
    return registerUser(data);
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutUser();
    } catch {
      // Safe error suppression during teardown
    }

    clearStoredSession();

    setUser(null);
    setToken(null);
    setOrganizations([]);
    setActiveOrgId(null);
  }, []);

  const selectOrg = useCallback((orgId: string) => {
    setActiveOrgId(orgId);
    if (typeof window !== "undefined") {
      localStorage.setItem(ACTIVE_ORG_KEY, orgId);
    }
  }, []);

  const createOrg = useCallback(
    async (data: CreateOrganizationInput) => {
      if (!token) throw new Error("Authentication required to create organization");
      const newOrg = await createOrganization(data, token);
      setOrganizations((prev) => [...prev, newOrg]);
      setActiveOrgId(newOrg.id);
      if (typeof window !== "undefined") {
        localStorage.setItem(ACTIVE_ORG_KEY, newOrg.id);
      }
      return newOrg;
    },
    [token]
  );

  const refetchOrganizations = useCallback(async () => {
    if (!token) return [];
    const orgs = await listOrganizations(token);
    setOrganizations(orgs);
    return orgs;
  }, [token]);

  const activeOrg = useMemo(() => {
    return organizations.find((o) => o.id === activeOrgId) || null;
  }, [organizations, activeOrgId]);

  const activeRole = useMemo(() => {
    return activeOrg?.role || null;
  }, [activeOrg]);

  const value = useMemo(
    () => ({
      user,
      token,
      organizations,
      activeOrg,
      activeOrgId,
      activeRole,
      isLoading,
      isAuthenticated: !!token && !!user,
      login,
      register,
      logout,
      createOrg,
      selectOrg,
      refetchOrganizations,
    }),
    [
      user,
      token,
      organizations,
      activeOrg,
      activeOrgId,
      activeRole,
      isLoading,
      login,
      register,
      logout,
      createOrg,
      selectOrg,
      refetchOrganizations,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
