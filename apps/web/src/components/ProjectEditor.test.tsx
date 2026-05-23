import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PreviewCanvas } from "./ProjectEditor";

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
