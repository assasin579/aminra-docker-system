/**
 * Mobile responsive audit — programmatic check for:
 *  - Horizontal scroll (page wider than viewport)
 *  - Tiny tap targets (< 32×32 px)
 *  - Off-screen content (left or right)
 *  - Missing viewport meta tag
 *
 * Runs ON MOBILE PROJECTS ONLY (mobile-chrome + mobile-safari).
 * Failures dumped to console + saved as JSON for triage.
 */
import { test, expect, type Page } from "@playwright/test";

// Skip on desktop projects
test.beforeEach(async ({}, testInfo) => {
  const proj = testInfo.project.name;
  test.skip(
    !proj.startsWith("mobile") && proj !== "tablet",
    "mobile responsive audit only runs on mobile/tablet projects",
  );
});

const PUBLIC_PAGES = [
  { path: "/",                       name: "landing" },
  { path: "/business/login",         name: "business-login" },
  { path: "/business/register",      name: "business-register" },
  { path: "/provider/login",         name: "provider-login" },
  { path: "/provider/register",      name: "provider-register" },
  { path: "/forgot-password",        name: "forgot-password" },
  { path: "/reset-password",         name: "reset-password" },
  { path: "/privacy",                name: "privacy" },
  { path: "/terms",                  name: "terms" },
  { path: "/chat",                   name: "chat" },
  { path: "/verify/HALAL-2026-DEMO", name: "verify-cert-active" },
  { path: "/verify/HALAL-NOT-EXIST", name: "verify-cert-404" },
];

interface AuditFinding {
  page: string;
  issue: string;
  details: string;
  severity: "critical" | "high" | "medium" | "low";
}

async function auditPage(page: Page, name: string): Promise<AuditFinding[]> {
  const findings: AuditFinding[] = [];
  const viewport = page.viewportSize();
  if (!viewport) return findings;

  // 1. Horizontal scroll check
  const docWidth = await page.evaluate(() => ({
    docW: document.documentElement.scrollWidth,
    bodyW: document.body.scrollWidth,
    viewportW: window.innerWidth,
  }));
  if (docWidth.docW > viewport.width + 1) {
    findings.push({
      page: name,
      issue: "horizontal-scroll",
      details: `documentWidth=${docWidth.docW}px > viewport=${viewport.width}px (overflow ${docWidth.docW - viewport.width}px)`,
      severity: "high",
    });
  }

  // 2. Viewport meta tag
  const hasViewportMeta = await page.evaluate(() =>
    !!document.querySelector('meta[name="viewport"]'));
  if (!hasViewportMeta) {
    findings.push({
      page: name,
      issue: "missing-viewport-meta",
      details: "No <meta name=viewport> — mobile rendering at desktop scale",
      severity: "critical",
    });
  }

  // 3. Tiny tap targets — all interactive elements
  // Skip checkbox/radio that are wrapped in a clickable <label> — the label
  // is the effective tap target, even if the visual input is small.
  const tinyTargets = await page.evaluate(() => {
    const interactive = document.querySelectorAll(
      'a, button, input[type="checkbox"], input[type="radio"], select, [role="button"]'
    );
    const tiny: { tag: string; size: string; text: string }[] = [];
    interactive.forEach(el => {
      const rect = (el as HTMLElement).getBoundingClientRect();
      // Apple HIG: 44×44, Google: 48×48, we use 32×32 as critical threshold
      if (rect.width > 0 && rect.height > 0
          && (rect.width < 32 || rect.height < 32)) {
        // For checkbox/radio: if a parent <label> is large enough, the label
        // is the effective tap target — skip this finding.
        const tag = el.tagName.toLowerCase();
        if (tag === "input") {
          const labelParent = el.closest("label");
          if (labelParent) {
            const labelRect = labelParent.getBoundingClientRect();
            if (labelRect.width >= 32 && labelRect.height >= 32) return;
          }
        }
        tiny.push({
          tag,
          size: `${Math.round(rect.width)}×${Math.round(rect.height)}`,
          text: (el.textContent || (el as HTMLInputElement).value || "").trim().slice(0, 30),
        });
      }
    });
    return tiny;
  });

  if (tinyTargets.length > 0) {
    findings.push({
      page: name,
      issue: "tiny-tap-targets",
      details: `${tinyTargets.length} target(s) under 32px: ` +
        tinyTargets.slice(0, 3).map(t => `${t.tag}(${t.size}) "${t.text}"`).join("; "),
      severity: "medium",
    });
  }

  // 4. Off-screen content (negative left or right > viewport)
  const offscreen = await page.evaluate((vw) => {
    const all = document.querySelectorAll("*");
    let count = 0;
    for (const el of all) {
      const rect = (el as HTMLElement).getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;
      // Element extends beyond viewport on right
      if (rect.right > vw + 5) count++;
    }
    return count;
  }, viewport.width);

  if (offscreen > 5) {  // some shadow/decoration is normal
    findings.push({
      page: name,
      issue: "many-elements-overflow-viewport",
      details: `${offscreen} element(s) extend past viewport right edge`,
      severity: "medium",
    });
  }

  // 5. Text size — body should be ≥ 14px on mobile
  const tinyText = await page.evaluate(() => {
    const all = document.querySelectorAll("p, span, label, li, td, div");
    let count = 0;
    for (const el of all) {
      const text = el.textContent?.trim();
      if (!text || text.length < 5) continue;
      const fontSize = parseFloat(getComputedStyle(el as HTMLElement).fontSize);
      if (fontSize > 0 && fontSize < 12) count++;
    }
    return count;
  });
  if (tinyText > 5) {
    findings.push({
      page: name,
      issue: "text-too-small",
      details: `${tinyText} text element(s) under 12px font-size`,
      severity: "low",
    });
  }

  return findings;
}

const allFindings: AuditFinding[] = [];

for (const { path, name } of PUBLIC_PAGES) {
  test(`${name}: mobile responsive checks`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");

    const findings = await auditPage(page, name);
    allFindings.push(...findings);

    // Always log; only FAIL on critical
    if (findings.length > 0) {
      console.log(`\n[mobile-audit:${name}]`);
      for (const f of findings) {
        console.log(`  [${f.severity}] ${f.issue}: ${f.details}`);
      }
    }

    // Regression gate: critical or high fails immediately.
    // Medium tap-target findings also fail — Stage 3 audit fixed all of them,
    // so any new finding indicates a regression.
    const critical = findings.filter(f => f.severity === "critical");
    expect(critical, `Critical mobile issues on ${name}`).toEqual([]);
    const high = findings.filter(f => f.severity === "high");
    expect(high, `High mobile issues on ${name}`).toEqual([]);
    const tapTargets = findings.filter(f => f.issue === "tiny-tap-targets");
    expect(tapTargets, `Tap-target regression on ${name}`).toEqual([]);
  });
}

test.afterAll(async () => {
  if (allFindings.length === 0) return;

  // Group by severity
  const bySeverity: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  allFindings.forEach(f => bySeverity[f.severity]++);

  console.log("\n═════════════════════════════════════════════════════════════════");
  console.log("  MOBILE RESPONSIVE AUDIT SUMMARY");
  console.log("═════════════════════════════════════════════════════════════════");
  console.log(`  CRITICAL: ${bySeverity.critical}  HIGH: ${bySeverity.high}  ` +
              `MEDIUM: ${bySeverity.medium}  LOW: ${bySeverity.low}`);
  console.log(`  Total findings: ${allFindings.length} across ${PUBLIC_PAGES.length} pages`);
  console.log("═════════════════════════════════════════════════════════════════\n");
});
