import { useQuery } from "@tanstack/react-query";
import { getDashboard } from "@/lib/api/dashboard";

export const dashboardQueryKeys = {
  all: (orgId: string) => ["dashboard", orgId] as const,
  summary: (
    orgId: string,
    filters?: {
      period?: string;
      startDate?: string;
      endDate?: string;
      lowStockThreshold?: number;
    }
  ) => [...dashboardQueryKeys.all(orgId), "summary", filters] as const,
};

export function useDashboard(
  orgId: string,
  params?: {
    period?: string;
    startDate?: string;
    endDate?: string;
    lowStockThreshold?: number;
  },
  token?: string
) {
  return useQuery({
    queryKey: dashboardQueryKeys.summary(orgId, params),
    queryFn: () => getDashboard(orgId, params, token),
    enabled: !!orgId,
  });
}
