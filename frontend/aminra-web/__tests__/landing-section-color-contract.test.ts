import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const page = readFileSync(resolve(process.cwd(), "app/landing/page.tsx"), "utf8");
const news = readFileSync(resolve(process.cwd(), "components/landing/LandingNews.tsx"), "utf8");

function sectionContaining(source: string, marker: string) {
  const markerIndex = source.indexOf(marker);
  expect(markerIndex).toBeGreaterThanOrEqual(0);
  const start = source.lastIndexOf("<section", markerIndex);
  const end = source.indexOf("</section>", markerIndex);
  expect(start).toBeGreaterThanOrEqual(0);
  expect(end).toBeGreaterThan(start);
  return source.slice(start, end + "</section>".length);
}

describe("landing section background rhythm", () => {
  it("keeps News white between the beige certification process and beige CTA", () => {
    const newsSection = sectionContaining(news, 'data-section="landing-news"');
    const processSection = sectionContaining(page, 't("landing.process_title")');
    const ctaSection = sectionContaining(page, "landing.cta_title");

    expect(newsSection).toContain('background: "#FFFFFF"');
    expect(processSection).toContain('background: "#F5F1E8"');
    expect(ctaSection).toContain('background: "#F5F1E8"');
  });
});
