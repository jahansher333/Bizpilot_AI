import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import React from "react";

import { NotFoundState, OfflineNotice, ServerErrorState, errorReference } from "@/components/ui/page-states";
import RootError from "@/app/error";
import RootNotFound from "@/app/not-found";

vi.mock("next/navigation", () => ({ useParams: () => ({ organization_id: "org-1" }) }));

describe("Page states (R10a)", () => {
  it("not found explains and links home", () => {
    render(<NotFoundState homeHref="/workspace/org-1" />);
    expect(screen.getByRole("heading", { name: "We couldn’t find that page" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to dashboard" })).toHaveAttribute("href", "/workspace/org-1");
  });

  it("server error shows a short reference code, never the raw message, and retries", () => {
    const onRetry = vi.fn();
    const error = Object.assign(new Error("relation \"orders\" does not exist"), { digest: "8f2a91c3d4e5" });
    render(<ServerErrorState error={error} onRetry={onRetry} homeHref="/workspaces" />);
    expect(screen.getByRole("alert")).toHaveTextContent("Your data is safe");
    expect(screen.getByText("8F2A91C3")).toBeInTheDocument();
    expect(screen.queryByText(/relation/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalled();
    expect(errorReference({})).toBe("CLIENT");
  });

  it("root error boundary uses retry(), falling back to reset()", () => {
    const reset = vi.fn();
    render(<RootError error={new Error("boom")} reset={reset} />);
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(reset).toHaveBeenCalled();
  });

  it("root not-found renders the shared state", () => {
    render(<RootNotFound />);
    expect(screen.getByRole("link", { name: "Go to dashboard" })).toHaveAttribute("href", "/workspaces");
  });

  it("shows the offline notice only while offline", () => {
    const onLine = vi.spyOn(window.navigator, "onLine", "get").mockReturnValue(true);
    render(<OfflineNotice />);
    expect(screen.queryByText("You’re offline")).not.toBeInTheDocument();

    onLine.mockReturnValue(false);
    act(() => void window.dispatchEvent(new Event("offline")));
    expect(screen.getByRole("status")).toHaveTextContent("You’re offline");

    onLine.mockReturnValue(true);
    act(() => void window.dispatchEvent(new Event("online")));
    expect(screen.queryByText("You’re offline")).not.toBeInTheDocument();
    onLine.mockRestore();
  });
});
