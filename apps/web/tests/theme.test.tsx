import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

import { THEME_KEY, THEME_SCRIPT, readThemePreference, resolveTheme, setThemePreference, watchSystemTheme } from "@/lib/theme";
import { SettingsView } from "@/components/settings/settings-view";

vi.mock("@/hooks/use-auth", () => ({
  useOptionalAuth: () => ({ user: { id: "u1", email: "owner@shop.pk", display_name: "Owner Khan" }, organizations: [{ id: "org-1", display_name: "Khan Traders", currency_code: "PKR", timezone: "Asia/Karachi", role: "owner" }], token: "t", logout: vi.fn() }),
  useAuth: () => ({ organizations: [{ id: "org-1", role: "owner" }] }),
}));
vi.mock("@/lib/api/auth", () => ({ logoutAllSessions: vi.fn() }));

let systemDark = false;
const listeners = new Set<() => void>();
const original = window.matchMedia;

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  systemDark = false;
  listeners.clear();
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    get matches() {
      return query.includes("dark") && systemDark;
    },
    media: query,
    addEventListener: (_: string, fn: () => void) => listeners.add(fn),
    removeEventListener: (_: string, fn: () => void) => listeners.delete(fn),
  })) as any;
});
afterEach(() => {
  window.matchMedia = original;
});

describe("Theme (R10c)", () => {
  it("follows the system by default and honours an explicit choice", () => {
    expect(readThemePreference()).toBe("system");
    expect(resolveTheme("system")).toBe("light");
    systemDark = true;
    expect(resolveTheme("system")).toBe("dark");
    expect(resolveTheme("light")).toBe("light");
  });

  it("stores the choice on this device and applies it to <html>", () => {
    setThemePreference("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    setThemePreference("system");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("the inline head script resolves the same way before first paint", () => {
    const run = () => new Function(THEME_SCRIPT)();
    run();
    expect(document.documentElement.dataset.theme).toBe("light");
    systemDark = true;
    run();
    expect(document.documentElement.dataset.theme).toBe("dark");
    localStorage.setItem(THEME_KEY, "light");
    run();
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("re-applies when the OS setting changes, only while following the system", () => {
    const stop = watchSystemTheme();
    systemDark = true;
    listeners.forEach((fn) => fn());
    expect(document.documentElement.dataset.theme).toBe("dark");
    setThemePreference("light");
    listeners.forEach((fn) => fn());
    expect(document.documentElement.dataset.theme).toBe("light");
    stop();
    expect(listeners.size).toBe(0);
  });

  it("Settings › Your account offers System / Light / Dark", () => {
    render(<SettingsView orgId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Your account" }));
    expect(screen.getByRole("radio", { name: /System/ })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: /Dark/ }));
    expect(screen.getByRole("radio", { name: /Dark/ })).toBeChecked();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  });
});
