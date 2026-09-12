import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (relativePath: string) =>
  readFileSync(join(root, relativePath), "utf8");

describe("normal user auth is owned by AMINRA UI, not visible Keycloak pages", () => {
  it("normal auth pages do not mention or redirect to Keycloak", () => {
    for (const page of [
      "app/(auth)/business/login/page.tsx",
      "app/(auth)/provider/login/page.tsx",
      "app/(auth)/business/register/page.tsx",
      "app/(auth)/provider/register/page.tsx",
      "app/(auth)/forgot-password/page.tsx",
      "app/(auth)/reset-password/page.tsx",
    ]) {
      const src = read(page);
      expect(src).not.toContain("signinRedirect(");
      expect(src).not.toContain("KeycloakSsoButton");
      expect(src).not.toMatch(/Keycloak/i);
    }
  });

  it("landing CTAs route normal users to AMINRA auth pages, never directly to Keycloak", () => {
    const src = read("app/landing/page.tsx");
    expect(src).not.toContain("redirectToKeycloak");
    expect(src).not.toContain("signinRedirect(");
    expect(src).not.toContain("isOidcEnabled");
    expect(src).toContain('href="/business/register"');
    expect(src).toContain('href="/business/login"');
  });

  it("normal credential login is handled by a Next route that exchanges against Keycloak server-side and returns the app profile", () => {
    const routePath = "app/api/auth/login/route.ts";
    expect(existsSync(join(root, routePath))).toBe(true);
    const src = read(routePath);
    expect(src).toContain("grant_type");
    expect(src).toContain("password");
    expect(src).toContain("/protocol/openid-connect/token");
    expect(src).toContain("/auth/me");
    expect(src).not.toContain("signinRedirect");
  });

  it("normal user logout does not redirect to Keycloak when no browser OIDC user exists", () => {
    const src = read("components/UserAuthContext.tsx");
    expect(src).toContain("if (oidcUser) {");
    expect(src).toContain("await signoutRedirect(oidcUser)");
    expect(src).not.toContain("Always visit Keycloak end-session for interactive SSO logout");
  });
});
