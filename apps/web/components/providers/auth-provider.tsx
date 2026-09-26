"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from "react";
import {
  AuthTokens,
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
  refreshSessionToken,
  registerUser,
} from "@/lib/api/auth";
import {
  createOrganization,
  listOrganizations,
} from "@/lib/api/organizations";

const REFRESH_TOKEN_KEY = "bizpilot_refresh_token";
const ACTIVE_ORG_KEY = "bizpilot_active_org_id";

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

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserMe | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [activeOrgId, setActiveOrgId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize session on mount
  useEffect(() => {
    let isMounted = true;

    async function initSession() {
      try {
        const storedRefreshToken = typeof window !== "undefined"
          ? localStorage.getItem(REFRESH_TOKEN_KEY)
          : null;

        if (!storedRefreshToken) {
          if (isMounted) setIsLoading(false);
          return;
        }

        // Attempt refresh
        const tokenRes: AuthTokens = await refreshSessionToken(storedRefreshToken);
        if (!isMounted) return;

        setToken(tokenRes.access_token);
        setRefreshToken(tokenRes.refresh_token);
        if (typeof window !== "undefined") {
          localStorage.setItem(REFRESH_TOKEN_KEY, tokenRes.refresh_token);
        }

        // Fetch user and orgs
        const [me, orgs] = await Promise.all([
          getCurrentUser(tokenRes.access_token),
          listOrganizations(tokenRes.access_token),
        ]);

        if (!isMounted) return;
        setUser(me);
        setOrganizations(orgs);

        // Restore active org
        const storedOrgId = typeof window !== "undefined"
          ? localStorage.getItem(ACTIVE_ORG_KEY)
          : null;

        if (storedOrgId && orgs.some((o) => o.id === storedOrgId)) {
          setActiveOrgId(storedOrgId);
        } else if (orgs.length > 0) {
          setActiveOrgId(orgs[0].id);
          if (typeof window !== "undefined") {
            localStorage.setItem(ACTIVE_ORG_KEY, orgs[0].id);
          }
        }
      } catch {
        // Clear invalid session
        if (typeof window !== "undefined") {
          localStorage.removeItem(REFRESH_TOKEN_KEY);
          localStorage.removeItem(ACTIVE_ORG_KEY);
        }
        if (isMounted) {
          setUser(null);
          setToken(null);
          setRefreshToken(null);
          setOrganizations([]);
          setActiveOrgId(null);
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    initSession();

    return () => {
      isMounted = false;
    };
  }, []);

  const login = useCallback(async (credentials: LoginInput) => {
    setIsLoading(true);
    try {
      const tokens = await loginUser(credentials);
      setToken(tokens.access_token);
      setRefreshToken(tokens.refresh_token);

      if (typeof window !== "undefined") {
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
      }

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
    if (refreshToken) {
      try {
        await logoutUser(refreshToken, token || undefined);
      } catch {
        // Safe error suppression during teardown
      }
    }

    if (typeof window !== "undefined") {
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(ACTIVE_ORG_KEY);
    }

    setUser(null);
    setToken(null);
    setRefreshToken(null);
    setOrganizations([]);
    setActiveOrgId(null);
  }, [refreshToken, token]);

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
