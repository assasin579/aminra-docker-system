import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();

describe("UserAuthContext logout contract", () => {
  it("always redirects through Keycloak end-session when OIDC is enabled, even if local OIDC user is missing", () => {
    const src = readFileSync(join(root, "components/UserAuthContext.tsx"), "utf8");

    expect(src).toContain("const oidcUser = isOidcEnabled()");
    expect(src).toContain("await getOidcUser().catch(() => null)");
    expect(src).toContain("if (isOidcEnabled())");
    expect(src).toContain("await signoutRedirect(oidcUser)");
    expect(src).not.toContain("shouldEndKeycloakSession");
  });
});
