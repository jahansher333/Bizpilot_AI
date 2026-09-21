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
  it("renders the initial workspace route", () => {
    const view = render(<HomePage />);
    expect(view.getByRole("heading", { name: "Business workspace" })).toBeInTheDocument();
    expect(view.getByText("Your authenticated workspace is being prepared")).toBeInTheDocument();
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