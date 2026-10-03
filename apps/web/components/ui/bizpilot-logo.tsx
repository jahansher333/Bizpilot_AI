import React from "react";
import { Logo } from "@/components/ui/logo";

interface BizPilotLogoProps {
  size?: number | "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
}

/**
 * Compatibility wrapper for screens not yet migrated to the design system (R2–R8).
 * Renders the design canvas `Logo`; size/className are accepted but no longer used.
 */
export function BizPilotLogo({ showText = false }: BizPilotLogoProps) {
  return <Logo showText={showText} />;
}
