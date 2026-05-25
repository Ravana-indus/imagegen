import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { apiRequest } from "@/lib/api";
import { GeneratedImagesGallery } from "./GeneratedImagesGallery";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

describe("GeneratedImagesGallery", () => {
  it("shows generated images with names and details", async () => {
    vi.mocked(apiRequest).mockResolvedValue([
      {
        id: "item-1",
        project_id: "project-1",
        project_name: "Summer range",
        name: "Summer range - Product 1",
        status: "generated",
        item_index: 1,
        attempt_count: 1,
        created_at: "2026-05-24T00:00:00Z",
        preview_url: "https://assets.test/base.png",
        source_product_asset_key: "sources/projects/project-1/products/one.png",
      },
    ]);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <GeneratedImagesGallery />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Summer range - Product 1" })).toBeInTheDocument(),
    );
    expect(screen.getByText("Summer range")).toBeInTheDocument();
    expect(screen.getByText("generated")).toBeInTheDocument();
    expect(screen.getByAltText("Summer range - Product 1")).toHaveAttribute(
      "src",
      "https://assets.test/base.png",
    );
  });
});
