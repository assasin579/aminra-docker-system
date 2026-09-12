import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("UserAuthContext logout contract", () => {
  it("only redirects through the identity-provider end-session for a stored browser SSO session", () => {
    const src = readFileSync(join(root, "components/UserAuthContext.tsx"), "utf8");

    expect(src).toContain("const oidcUser = isOidcEnabled()");
    expect(src).toContain("await getOidcUser().catch(() => null)");
    expect(src).toContain("if (oidcUser)");
    expect(src).toContain("await signoutRedirect(oidcUser)");
    expect(src).not.toContain("if (isOidcEnabled()) {\n          // Always visit");
  });
});
