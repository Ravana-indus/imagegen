import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CreateProjectForm } from "./CreateProjectForm";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

describe("CreateProjectForm", () => {
  it("supports shared brand assets and multiple batch product images", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <CreateProjectForm />
      </QueryClientProvider>
    );

    expect(screen.getByLabelText("Background image")).toBeRequired();
    expect(screen.getByRole("button", { name: "Upload background to Supabase" })).toBeInTheDocument();
    expect(screen.getByLabelText("Brand logo")).toBeRequired();
    expect(screen.getByLabelText("Flag image")).toBeRequired();
    fireEvent.click(screen.getByRole("radio", { name: "Batch" }));
    expect(screen.getByLabelText(/Product image/)).toHaveAttribute("multiple");
    expect(screen.getByRole("button", { name: "Upload product to Supabase" })).toBeInTheDocument();
  });
});
