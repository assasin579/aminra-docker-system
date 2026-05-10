/**
 * Component tests for KeycloakSsoButton + KeycloakSsoNotice (Phase 2c).
 *
 * Mocks lib/auth-oidc to verify gating + click handling without
 * pulling in oidc-client-ts.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const hoisted = vi.hoisted(() => ({
  isOidcEnabled: vi.fn(),
  signinRedirect: vi.fn(),
}));

vi.mock("@/lib/auth-oidc", () => ({
  isOidcEnabled: hoisted.isOidcEnabled,
  signinRedirect: hoisted.signinRedirect,
}));

import {
  KeycloakSsoButton,
  KeycloakSsoNotice,
} from "@/components/KeycloakSsoButton";

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("KeycloakSsoButton", () => {
  it("renders nothing when flag off", () => {
    hoisted.isOidcEnabled.mockReturnValue(false);
    const { container } = render(<KeycloakSsoButton returnTo="/x" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders button + divider + hint when flag on", () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    render(<KeycloakSsoButton returnTo="/dashboard/business" />);
    expect(screen.getByTestId("keycloak-sso-button")).toBeInTheDocument();
    expect(screen.getByText("HOẶC")).toBeInTheDocument();
    expect(
      screen.getByText(/Bao gồm xác thực 2 yếu tố/i),
    ).toBeInTheDocument();
  });

  it("uses custom label + hint props", () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    render(
      <KeycloakSsoButton
        returnTo="/x"
        label="Sign in with SSO"
        hint="custom hint"
      />,
    );
    expect(screen.getByText("Sign in with SSO")).toBeInTheDocument();
    expect(screen.getByText("custom hint")).toBeInTheDocument();
  });

  it("calls signinRedirect with the supplied returnTo on click", async () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    hoisted.signinRedirect.mockResolvedValue(undefined);
    render(<KeycloakSsoButton returnTo="/dashboard/provider" />);
    fireEvent.click(screen.getByTestId("keycloak-sso-button"));
    await waitFor(() => {
      expect(hoisted.signinRedirect).toHaveBeenCalledWith(
        "/dashboard/provider",
      );
    });
  });

  it("surfaces error from signinRedirect to the user", async () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    hoisted.signinRedirect.mockRejectedValue(new Error("network down"));
    render(<KeycloakSsoButton returnTo="/x" />);
    fireEvent.click(screen.getByTestId("keycloak-sso-button"));
    await waitFor(() => {
      expect(screen.getByText("network down")).toBeInTheDocument();
    });
  });
});

describe("KeycloakSsoNotice", () => {
  it("renders nothing when flag off", () => {
    hoisted.isOidcEnabled.mockReturnValue(false);
    const { container } = render(<KeycloakSsoNotice />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders notice + CTA link when flag on", () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_URL", "https://auth.aminra.vn");
    vi.stubEnv("NEXT_PUBLIC_KEYCLOAK_REALM", "aminra");
    render(<KeycloakSsoNotice />);
    const cta = screen.getByTestId("keycloak-account-cta");
    expect(cta).toHaveAttribute(
      "href",
      "https://auth.aminra.vn/realms/aminra/account/#/security/signing-in",
    );
    expect(cta).toHaveAttribute("target", "_blank");
    expect(cta).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("uses custom CTA href when supplied", () => {
    hoisted.isOidcEnabled.mockReturnValue(true);
    render(
      <KeycloakSsoNotice
        ctaHref="https://example.com/reset"
        ctaLabel="Reset on Keycloak"
      />,
    );
    expect(screen.getByTestId("keycloak-account-cta")).toHaveAttribute(
      "href",
      "https://example.com/reset",
    );
    expect(screen.getByText(/Reset on Keycloak/)).toBeInTheDocument();
  });
});
