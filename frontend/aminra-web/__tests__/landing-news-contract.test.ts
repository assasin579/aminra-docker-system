import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import i18n from "../lib/i18n";

const read = (file: string) => readFileSync(resolve(process.cwd(), file), "utf8");

describe("landing news section contract", () => {
  it("renders three image-led news cards with accessible paging before the final CTA", () => {
    const page = read("app/landing/page.tsx");
    const component = read("components/landing/LandingNews.tsx");
    expect(page).toContain("<LandingNews />");
    expect(page.indexOf("<LandingNews />")).toBeLessThan(page.indexOf("landing.cta_title"));
    expect(component).toContain('data-section="landing-news"');
    expect(component).toContain("NEWS_PER_PAGE = 3");
    expect(component).toContain('aria-label={t("landing.landing_news.pagination")}');
    expect(component).toContain("aria-live=\"polite\"");
    expect(component).toContain("prefers-reduced-motion: reduce");
    expect(component).toContain('matchMedia?.("(prefers-reduced-motion: reduce)")');
    expect(component).toContain("onMouseEnter={() => setPaused(true)}");
    expect(component).toContain('t("landing.landing_news.demo_notice")');
    expect(component).not.toContain("images.unsplash.com");
    for (const image of ["market", "business", "traceability", "certification", "readiness", "trade"]) {
      expect(component).toContain(`/news/${image}.jpg`);
      expect(read(`public/news/${image}.jpg`).length).toBeGreaterThan(10_000);
    }
    const translations = read("lib/i18n.ts");
    expect(translations.match(/demo_notice:/g)).toHaveLength(4);
  });

  it("resolves the editorial demo notice in every supported locale", () => {
    const expected = {
      en: "Illustrative demo content — not current news.",
      vi: "Nội dung minh họa — không phải tin tức cập nhật.",
      ms: "Kandungan ilustrasi — bukan berita semasa.",
      ar: "محتوى توضيحي — ليس أخباراً حديثة.",
    };
    for (const [lng, text] of Object.entries(expected)) {
      expect(i18n.t("landing.landing_news.demo_notice", { lng })).toBe(text);
    }
  });
});
