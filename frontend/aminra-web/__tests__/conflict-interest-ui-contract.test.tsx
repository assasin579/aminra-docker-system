import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Conflict interest UI contract", () => {
  it("exposes durable conflict register markers and required override reason", () => {
    const source = readFileSync(join(process.cwd(), "app/conflicts/page.tsx"), "utf8");

    expect(source).toContain('data-testid="conflict-interest-register-page"');
    expect(source).toContain('data-api-path="/api/conflicts"');
    expect(source).toContain('data-api-path="/api/conflicts/{id}/review"');
    expect(source).toContain('data-api-path="/api/conflicts/{id}/override"');
    expect(source).toContain('data-marker="unresolved-conflicts-block"');
    expect(source).toContain('data-marker="cleared-conflicts-allow"');
    expect(source).toContain('data-marker="overridden-conflicts-audit"');
    expect(source).toContain('data-marker="cross-provider-scope"');
    expect(source).toContain('name="override_reason"');
    expect(source).toContain('data-testid="conflict-override-reason-required"');
    expect(source).toMatch(/name="override_reason"[\s\S]*required/);
  });
});
