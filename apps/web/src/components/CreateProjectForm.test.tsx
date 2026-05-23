import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CreateProjectForm } from "./CreateProjectForm";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("CreateProjectForm", () => {
  it("supports shared brand assets and multiple batch product images", () => {
    render(<CreateProjectForm />);

    expect(screen.getByLabelText("Background image")).toBeRequired();
    expect(screen.getByLabelText("Brand logo")).toBeRequired();
    expect(screen.getByLabelText("Country flag")).toBeRequired();
    fireEvent.click(screen.getByRole("radio", { name: "Batch" }));
    expect(screen.getByLabelText(/Product image/)).toHaveAttribute("multiple");
  });
});
