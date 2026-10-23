import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file: string) => readFileSync(resolve(process.cwd(), file), "utf8");

describe("landing news section contract", () => {
  it("renders three image-led news cards with accessible paging before the final CTA", () => {
    const page = read("app/landing/page.tsx");
    const component = read("components/landing/LandingNews.tsx");
    expect(page).toContain("<LandingNews />");
    expect(page.indexOf("<LandingNews />")).toBeLessThan(page.indexOf("landing.cta_title"));
    expect(component).toContain('data-section="landing-news"');
    expect(component).toContain("NEWS_PER_PAGE = 3");
    expect(component).toContain('aria-label={t("landing_news.pagination")}');
    expect(component).toContain("aria-live=\"polite\"");
    expect(component).toContain("prefers-reduced-motion: reduce");
    expect(component).toContain('matchMedia?.("(prefers-reduced-motion: reduce)")');
    expect(component).toContain("onMouseEnter={() => setPaused(true)}");
    expect(component).toContain('t("landing_news.demo_notice")');
    expect(component).not.toContain("images.unsplash.com");
    for (const image of ["market", "business", "traceability", "certification", "readiness", "trade"]) {
      expect(component).toContain(`/news/${image}.jpg`);
      expect(read(`public/news/${image}.jpg`).length).toBeGreaterThan(10_000);
    }
    const translations = read("lib/i18n.ts");
    expect(translations.match(/demo_notice:/g)).toHaveLength(4);
  });
});
