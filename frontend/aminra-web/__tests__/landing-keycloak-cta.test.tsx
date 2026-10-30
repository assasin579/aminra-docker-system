import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LandingPage from "@/app/landing/page";

const auth = vi.hoisted(() => ({
  isOidcEnabled: vi.fn(),
  signinRedirect: vi.fn(),
}));

vi.mock("@/lib/auth-oidc", () => auth);

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    i18n: { language: "vi", changeLanguage: vi.fn() },
    t: (key: string) => {
      const labels: Record<string, string> = {
        "landing.cta_start": "Bắt đầu ngay",
        "landing.cta_button": "Bắt đầu ngay",
        "landing.cta_login": "Đăng nhập",
        "landing.hero_title": "AMINRA",
        "landing.hero_subtitle": "Halal Integrity, Digital Trust",
      };
      return labels[key] ?? key;
    },
  }),
}));

class MockIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds = [];
  disconnect = vi.fn();
  observe = vi.fn();
  takeRecords = vi.fn(() => []);
  unobserve = vi.fn();
}

describe("landing normal-user CTA", () => {
  beforeEach(() => {
    auth.isOidcEnabled.mockReset();
    auth.signinRedirect.mockReset();
    auth.signinRedirect.mockResolvedValue(undefined);

    Object.defineProperty(window, "IntersectionObserver", {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });
    Object.defineProperty(globalThis, "IntersectionObserver", {
      configurable: true,
      writable: true,
      value: MockIntersectionObserver,
    });
    Object.defineProperty(window.HTMLCanvasElement.prototype, "getContext", {
      configurable: true,
      value: vi.fn(() => ({
        clearRect: vi.fn(),
        arc: vi.fn(),
        fill: vi.fn(),
        beginPath: vi.fn(),
        moveTo: vi.fn(),
        lineTo: vi.fn(),
        stroke: vi.fn(),
        closePath: vi.fn(),
      })),
    });
    Object.defineProperty(window, "requestAnimationFrame", {
      configurable: true,
      writable: true,
      value: vi.fn(() => 1),
    });
    Object.defineProperty(window, "cancelAnimationFrame", {
      configurable: true,
      writable: true,
      value: vi.fn(),
    });
  });

  it("keeps the hero CTA inside AMINRA auth even when OIDC is enabled", () => {
    auth.isOidcEnabled.mockReturnValue(true);

    render(<LandingPage />);

    const [heroCta] = screen.getAllByRole("link", { name: /bắt đầu ngay/i });
    expect(heroCta).toHaveAttribute("href", "/business/register");

    const clickWasNotCancelled = fireEvent.click(heroCta);

    expect(clickWasNotCancelled).toBe(true);
    expect(auth.signinRedirect).not.toHaveBeenCalled();
  });

  it("also keeps the lower-page CTA inside AMINRA auth", () => {
    auth.isOidcEnabled.mockReturnValue(true);

    render(<LandingPage />);

    const ctas = screen.getAllByRole("link", { name: /bắt đầu ngay/i });
    expect(ctas.length).toBeGreaterThanOrEqual(2);

    const clickWasNotCancelled = fireEvent.click(ctas[1]);

    expect(ctas[1]).toHaveAttribute("href", "/business/register");
    expect(clickWasNotCancelled).toBe(true);
    expect(auth.signinRedirect).not.toHaveBeenCalled();
  });
});
