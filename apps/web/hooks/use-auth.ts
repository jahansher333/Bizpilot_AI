"use client";

import { useContext } from "react";
import { AuthContext, type AuthContextType } from "@/components/providers/auth-provider";

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

/** For presentational details (e.g. a greeting) that must not fail outside an AuthProvider. */
export function useOptionalAuth(): AuthContextType | null {
  return useContext(AuthContext) ?? null;
}

export type { AuthContextType };
