import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

describe("Complaints and appeals UI contract", () => {
  it("exposes durable complaints and appeals markers", () => {
    const source = readFileSync(join(process.cwd(), "app/complaints/page.tsx"), "utf8");

    expect(source).toContain('data-testid="complaints-appeals-page"');
    expect(source).toContain('data-testid="complaint-queue"');
    expect(source).toContain('data-api-path="/api/complaints"');
    expect(source).toContain('data-api-path="/api/complaints/{id}/assign"');
    expect(source).toContain('data-api-path="/api/complaints/{id}/transition"');
    expect(source).toContain('data-api-path="/api/complaints/{id}/events"');
    expect(source).toContain('data-marker="appeal-original-decision-requirement"');
    expect(source).toContain('name="original_decision_id"');
    expect(source).toContain('data-testid="appeal-original-decision-required"');
    expect(source).toContain('name="owner_id"');
    expect(source).toContain('data-testid="assignment-owner-field"');
    expect(source).toContain('data-marker="transition-controls"');
    expect(source).toContain('name="closure_reason"');
    expect(source).toContain('data-testid="closure-reason-required"');
    expect(source).toContain('data-marker="append-only-events"');
  });
});
