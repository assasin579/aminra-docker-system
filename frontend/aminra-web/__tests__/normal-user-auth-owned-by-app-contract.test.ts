import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const root = process.cwd();
const read = (relativePath: string) =>
  readFileSync(join(root, relativePath), "utf8");

describe("normal user auth is owned by AMINRA UI, not visible Keycloak pages", () => {
  it("business and provider login pages expose a reusable route back to the public landing page", () => {
    const componentPath = "components/auth/BackToLandingLink.tsx";
    expect(existsSync(join(root, componentPath))).toBe(true);

    const component = read(componentPath);
    expect(component).toContain('href = "/landing"');
    expect(component).toContain('label = "Về trang chủ"');
    expect(component).toContain('aria-label={label}');
    expect(component).toContain('data-auth-exit="landing"');

    for (const page of [
      "app/(auth)/business/login/page.tsx",
      "app/(auth)/provider/login/page.tsx",
    ]) {
      const src = read(page);
      expect(src).toContain('BackToLandingLink');
      expect(src).toContain('data-auth-exit-slot="landing"');
    }
  });

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

  it("Playwright helpers do not call retired backend login endpoints", () => {
    for (const path of [
      "e2e/fixtures.ts",
      "e2e/02-auth.spec.ts",
      "e2e/17-mvp-demo-public.spec.ts",
      "e2e/18-mvp-demo-provider-admin.spec.ts",
    ]) {
      const src = read(path);
      expect(src).not.toContain('"/auth/login"');
      expect(src).not.toContain('"/admin/login"');
    }

    const authHelper = read("e2e/helpers/auth-token.ts");
    expect(authHelper).toContain("/protocol/openid-connect/token");
    expect(authHelper).not.toContain('"/auth/login"');
    expect(authHelper).not.toContain('"/admin/login"');
  });

  it("normal user logout does not redirect to Keycloak when no browser OIDC user exists", () => {
    const src = read("components/UserAuthContext.tsx");
    expect(src).toContain("if (oidcUser) {");
    expect(src).toContain("await signoutRedirect(oidcUser)");
    expect(src).not.toContain("Always visit Keycloak end-session for interactive SSO logout");
  });
});
