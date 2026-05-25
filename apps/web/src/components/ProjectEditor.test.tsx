import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { apiRequest } from "@/lib/api";
import { PreviewCanvas, ProjectEditor } from "./ProjectEditor";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

describe("PreviewCanvas", () => {
  it("renders generated artwork with exact logo and flag overlays", () => {
    render(
      <PreviewCanvas
        baseUrl="https://assets.test/base.png"
        logoUrl="https://assets.test/logo.png"
        flagUrl="https://assets.test/flag.png"
        layout={{
          revision: 1,
          logo_x: 0.05,
          logo_y: 0.05,
          logo_width: 0.22,
          logo_height: 0.12,
          logo_visible: true,
          flag_x: 0.82,
          flag_y: 0.05,
          flag_width: 0.13,
          flag_height: 0.09,
          flag_visible: true,
        }}
      />,
    );

    expect(screen.getByAltText("Generated base composition")).toBeInTheDocument();
    expect(screen.getByAltText("Brand logo overlay")).toBeInTheDocument();
    expect(screen.getByAltText("Country flag overlay")).toBeInTheDocument();
  });
});

describe("ProjectEditor", () => {
  it("offers prepare-all and zip-download actions for generated projects", async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      id: "project-1",
      name: "Campaign",
      mode: "batch",
      status: "completed",
      created_at: "2026-05-24T00:00:00Z",
      background_url: "https://assets.test/background.png",
      logo_url: "https://assets.test/logo.png",
      flag_url: "https://assets.test/flag.png",
      items: [
        {
          id: "item-1",
          status: "generated",
          attempt_count: 1,
          preview_url: "https://assets.test/base.png",
          error_message: null,
          layout: {
            revision: 1,
            logo_x: 0.05,
            logo_y: 0.05,
            logo_width: 0.22,
            logo_height: 0.12,
            logo_visible: true,
            flag_x: 0.82,
            flag_y: 0.05,
            flag_width: 0.13,
            flag_height: 0.09,
            flag_visible: true,
          },
        },
      ],
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <ProjectEditor projectId="project-1" />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("Campaign")).toBeInTheDocument());
    expect(
      screen.getByRole("button", { name: "Prepare all downloads" }),
    ).toBeEnabled();
    expect(screen.getByRole("button", { name: "Download all ZIP" })).toBeEnabled();
  });
});
