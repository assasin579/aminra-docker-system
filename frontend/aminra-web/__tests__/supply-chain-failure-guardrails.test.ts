import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const SUPPLY_CHAIN_PAGES = [
  "app/supply-chain/process/page.tsx",
  "app/supply-chain/materials/page.tsx",
  "app/supply-chain/batches/page.tsx",
];

describe("Supply-chain FE failure-handling guardrails", () => {
  for (const rel of SUPPLY_CHAIN_PAGES) {
    it(`${rel} routes write actions through shared apiFetch/apiJson wrapper`, () => {
      const src = readFileSync(join(process.cwd(), rel), "utf8");
      const unsafeRawWriteFetch = /fetch\([^;]+method:\s*["'](?:POST|PUT|DELETE)["']/s;
      expect(src, "Write actions must use apiFetch/apiJson so non-2xx cannot become false success").not.toMatch(
        unsafeRawWriteFetch,
      );
      expect(src, "Supply-chain write pages should import/use the shared API client").toMatch(/apiFetch|apiJson/);
    });
  }

  it("shared API client normalizes non-2xx and network failures", () => {
    const clientSrc = readFileSync(join(process.cwd(), "lib/apiClient.ts"), "utf8");
    expect(clientSrc).toContain("class ApiClientError");
    expect(clientSrc).toContain("parseApiError");
    expect(clientSrc).toMatch(/if \(!res\.ok\)/);
  });

  it("process create flow has explicit FE→BE contract coverage", () => {
    const testSrc = readFileSync(join(process.cwd(), "__tests__/supply-chain-process-create.test.tsx"), "utf8");
    expect(testSrc).toContain("/api/api/supply-chain/processes");
    expect(testSrc).toContain('findFetchCall("/api/api/supply-chain/processes", "POST")');
    expect(testSrc).toContain("Authorization");
    expect(testSrc).toContain("Content-Type");
  });

  it("live contract smoke covers create endpoints across supply-chain components", () => {
    const smokeSrc = readFileSync(join(process.cwd(), "e2e/40-supply-chain-create-contracts.spec.ts"), "utf8");
    for (const endpoint of ["/processes", "/suppliers", "/batches"]) {
      expect(smokeSrc).toContain(`/api/api/supply-chain${endpoint}`);
    }
  });
});
