import { describe, expect, it } from "vitest";
import { resolvePostLoginReturnTo } from "@/lib/auth-post-login-route";

describe("resolvePostLoginReturnTo", () => {
  it("keeps a platform admin on /admin when admin login started from admin route", () => {
    expect(
      resolvePostLoginReturnTo("/admin", {
        role: "provider",
        realm_roles: ["platform_admin"],
      }),
    ).toBe("/admin");
  });

  it("routes a platform admin to /admin instead of looping through business login/dashboard", () => {
    expect(
      resolvePostLoginReturnTo("/dashboard/business", {
        role: "provider",
        realm_roles: ["platform_admin"],
      }),
    ).toBe("/admin");
  });

  it("routes provider users away from business-only dashboards", () => {
    expect(
      resolvePostLoginReturnTo("/dashboard/business", {
        role: "provider",
        realm_roles: ["cb_admin"],
      }),
    ).toBe("/dashboard/provider");
  });

  it("routes business users away from provider-only dashboards", () => {
    expect(
      resolvePostLoginReturnTo("/dashboard/provider", {
        role: "business",
        realm_roles: ["business"],
      }),
    ).toBe("/dashboard/business");
  });

  it("rejects open redirects and falls back by authenticated role", () => {
    expect(
      resolvePostLoginReturnTo("https://evil.example", {
        role: "provider",
        realm_roles: ["platform_admin"],
      }),
    ).toBe("/admin");
  });
});
