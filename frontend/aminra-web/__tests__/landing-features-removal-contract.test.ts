import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("landing features section removal", () => {
  it("does not render the comprehensive-solutions block or keep its data mapping", () => {
    const page = readFileSync(resolve(process.cwd(), "app/landing/page.tsx"), "utf8");

    expect(page).not.toContain("t(\"landing.features_title\")");
    expect(page).not.toContain("const features = [");
    expect(page).not.toContain("{/* ── Features ── */}");
    expect(page).toContain("<LandingNews />");
  });
});
