import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchApiWithFallback } from "./api-fallback";

describe("fetchApiWithFallback", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.API_ORIGIN;
  });

  it("returns bundled data when the hosted API rejects a static endpoint", async () => {
    process.env.API_ORIGIN = "https://api.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ detail: "invalid UUID" }, { status: 422 }),
      ),
    );

    const response = await fetchApiWithFallback("/projects/generated-images", [
      { id: "local-image" },
    ]);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([{ id: "local-image" }]);
  });

  it("uses hosted API data when it is available", async () => {
    process.env.API_ORIGIN = "https://api.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json([{ id: "hosted-image" }])),
    );

    const response = await fetchApiWithFallback("/projects/generated-images", [
      { id: "local-image" },
    ]);

    expect(await response.json()).toEqual([{ id: "hosted-image" }]);
  });
});
