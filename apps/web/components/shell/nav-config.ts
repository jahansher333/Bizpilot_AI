import type { IconName } from "@/components/ui/icon";
import type { OrgRole } from "@/hooks/use-org-role";

export interface NavItem {
  key: string;
  label: string;
  href: string;
  icon: IconName;
  badge?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

/**
 * Sidebar structure from the design canvas (07 · Sidebar).
 * Hiding is convenience only; the backend authorises every request.
 */
export function buildNavGroups(orgId: string, role: OrgRole): NavGroup[] {
  const base = `/workspace/${orgId}`;
  const ownerOrManager = role === "owner" || role === "manager";

  const groups: NavGroup[] = [
    { label: "Overview", items: [{ key: "dashboard", label: "Dashboard", href: base, icon: "dashboard" }] },
    {
      label: "Operations",
      items: [
        { key: "orders", label: "Orders", href: `${base}/orders`, icon: "orders" },
        { key: "catalog", label: "Products", href: `${base}/catalog`, icon: "products" },
        { key: "inventory", label: "Inventory", href: `${base}/inventory`, icon: "inventory" },
        { key: "customers", label: "Customers", href: `${base}/customers`, icon: "customers" },
      ],
    },
    {
      label: "Finance",
      items: [
        { key: "payments", label: "Payments", href: `${base}/payments`, icon: "payments" },
        ...(ownerOrManager ? [{ key: "expenses", label: "Expenses", href: `${base}/expenses`, icon: "expenses" as const }] : []),
      ],
    },
    {
      label: "Intelligence",
      items: [{ key: "assistant", label: "BizPilot AI", href: `${base}/assistant`, icon: "ai", badge: "Read-only" }],
    },
  ];

  if (role === "owner") {
    groups.push({ label: "Management", items: [{ key: "team", label: "Team", href: `${base}/team`, icon: "team" }] });
  }
  return groups;
}

const SECTION_OF: Record<string, { section: string; page: string }> = {
  orders: { section: "Operations", page: "Orders" },
  catalog: { section: "Operations", page: "Products" },
  inventory: { section: "Operations", page: "Inventory" },
  customers: { section: "Operations", page: "Customers" },
  payments: { section: "Finance", page: "Payments" },
  expenses: { section: "Finance", page: "Expenses" },
  assistant: { section: "Intelligence", page: "BizPilot AI" },
  team: { section: "Management", page: "Team" },
};

/** Active nav key and breadcrumb for a workspace pathname. */
export function routeInfo(pathname: string | null, orgId: string): { key: string; section: string; page: string } {
  const prefix = `/workspace/${orgId}`;
  const rest = (pathname ?? "").startsWith(prefix) ? (pathname ?? "").slice(prefix.length) : "";
  const segment = rest.split("/").filter(Boolean)[0];
  if (segment && SECTION_OF[segment]) return { key: segment, ...SECTION_OF[segment] };
  return { key: "dashboard", section: "Overview", page: "Dashboard" };
}
