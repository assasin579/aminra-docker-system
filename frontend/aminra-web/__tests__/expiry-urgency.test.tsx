import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ExpiryUrgency from "@/components/certificates/ExpiryUrgency";

describe("ExpiryUrgency", () => {
  test("renders nothing for non-active status", () => {
    for (const status of ["suspended", "revoked", "expired"]) {
      const { container } = render(
        <ExpiryUrgency daysRemaining={5} status={status} />,
      );
      expect(container.firstChild).toBeNull();
    }
  });

  test("renders nothing for healthy active cert (>90 days)", () => {
    const { container } = render(
      <ExpiryUrgency daysRemaining={120} status="active" />,
    );
    expect(container.firstChild).toBeNull();
  });

  test("renders CAUTION badge at exactly 90 days", () => {
    render(<ExpiryUrgency daysRemaining={90} status="active" />);
    const badge = screen.getByText(/Còn 90d/);
    expect(badge.closest("span")).toHaveAttribute("data-urgency", "caution");
  });

  test("renders WARNING badge between 31-60 days", () => {
    render(<ExpiryUrgency daysRemaining={45} status="active" />);
    const badge = screen.getByText(/Còn 45d/);
    expect(badge.closest("span")).toHaveAttribute("data-urgency", "warning");
  });

  test("renders CRITICAL badge ≤ 30 days", () => {
    render(<ExpiryUrgency daysRemaining={15} status="active" />);
    const badge = screen.getByText(/Còn 15d/);
    expect(badge.closest("span")).toHaveAttribute("data-urgency", "critical");
  });

  test("renders EXPIRED badge at 0 or negative days", () => {
    render(<ExpiryUrgency daysRemaining={0} status="active" />);
    const badge = screen.getByText(/Đã hết hạn/);
    expect(badge.closest("span")).toHaveAttribute("data-urgency", "expired");
  });

  test("handles negative days (already expired)", () => {
    render(<ExpiryUrgency daysRemaining={-5} status="active" />);
    expect(screen.getByText(/Đã hết hạn/)).toBeInTheDocument();
  });
});
