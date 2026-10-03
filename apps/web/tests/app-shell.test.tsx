import { describe, expect, it } from "vitest";
import { QueryClient, useQueryClient } from "@tanstack/react-query";
import { render } from "@testing-library/react";

import HomePage from "@/app/page";
import { QueryProvider } from "@/components/providers/query-provider";

function QueryProbe() {
  const client = useQueryClient();
  return <output>{client instanceof QueryClient ? "query-ready" : "query-missing"}</output>;
}

describe("application shell", () => {
  it("renders the landing page with sign-up and sign-in entry points (R2)", () => {
    const view = render(<HomePage />);
    expect(view.getByRole("heading", { level: 1 })).toHaveTextContent(/run your business/i);
    expect(view.getByRole("link", { name: /start using bizpilot/i })).toHaveAttribute("href", "/register");
    expect(view.getAllByRole("link", { name: /^sign in$/i })[0]).toHaveAttribute("href", "/login");
    expect(view.getByRole("figure", { name: /example of a bizpilot workspace/i })).toBeInTheDocument();
  });

  it("provides a shared query client", () => {
    const view = render(
      <QueryProvider>
        <QueryProbe />
      </QueryProvider>,
    );
    expect(view.getByText("query-ready")).toBeInTheDocument();
  });
});