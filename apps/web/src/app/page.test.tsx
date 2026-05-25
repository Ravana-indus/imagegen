import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./page";

describe("HomePage", () => {
  it("opens the internal app without a sign-in step", () => {
    render(<HomePage />);

    expect(
      screen.getByRole("heading", { name: "Product Creative Generator" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open dashboard" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
  });
});
