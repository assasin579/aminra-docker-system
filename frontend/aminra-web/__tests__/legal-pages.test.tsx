/**
 * Smoke tests for static legal pages.
 *
 * Goal: catch regressions where required-by-law sections get accidentally
 * removed (e.g., during a UI redesign). The Vietnamese PDPL (Nghị định 13)
 * mandates: collection scope, purposes, retention, user rights, contact.
 */
import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PrivacyPage from "@/app/privacy/page";
import TermsPage from "@/app/terms/page";

describe("PrivacyPage", () => {
  test("renders heading + last-updated date", () => {
    render(<PrivacyPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Chính sách bảo mật/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2026-04-25/)).toBeInTheDocument();
  });

  test("contains all 10 mandated PDPL-aligned sections", () => {
    render(<PrivacyPage />);
    [
      "Phạm vi áp dụng",
      "Thông tin chúng tôi thu thập",
      "Mục đích sử dụng",
      "Chia sẻ dữ liệu với bên thứ ba",
      "Lưu trữ và bảo mật",
      "Quyền của người dùng",
      "Thời gian lưu trữ",
      "Cookies",
      "Thay đổi chính sách",
      "Liên hệ",
    ].forEach((section) => {
      expect(
        screen.getByRole("heading", { level: 2, name: new RegExp(section) }),
      ).toBeInTheDocument();
    });
  });

  test("mentions PDPL Nghị định 13/2023", () => {
    render(<PrivacyPage />);
    expect(screen.getByText(/13\/2023\/NĐ-CP/)).toBeInTheDocument();
  });

  test("provides privacy contact email", () => {
    render(<PrivacyPage />);
    const links = screen.getAllByRole("link", { name: /privacy@aminra\.vn/ });
    expect(links.length).toBeGreaterThan(0);
    expect(links[0]).toHaveAttribute("href", "mailto:privacy@aminra.vn");
  });

  test("cross-links to terms page", () => {
    render(<PrivacyPage />);
    expect(
      screen.getByRole("link", { name: /Điều khoản dịch vụ/ }),
    ).toHaveAttribute("href", "/terms");
  });
});

describe("TermsPage", () => {
  test("renders heading + last-updated date", () => {
    render(<TermsPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Điều khoản dịch vụ/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/2026-04-25/)).toBeInTheDocument();
  });

  test("contains all 12 required ToS sections", () => {
    render(<TermsPage />);
    [
      "Chấp nhận điều khoản",
      "Mô tả dịch vụ",
      "Trách nhiệm của người dùng",
      "Vai trò của tổ chức cấp chứng nhận",
      "Quyền sở hữu trí tuệ",
      "Phí dịch vụ",
      "Tính sẵn sàng",
      "Giới hạn trách nhiệm",
      "Đình chỉ và chấm dứt",
      "Luật áp dụng",
      "Thay đổi điều khoản",
      "Liên hệ",
    ].forEach((section) => {
      expect(
        screen.getByRole("heading", { level: 2, name: new RegExp(section) }),
      ).toBeInTheDocument();
    });
  });

  test("clarifies AMINRA does NOT directly issue Halal certificates", () => {
    const { container } = render(<TermsPage />);
    expect(container.textContent).toMatch(
      /AMINRA\s+không\s+trực tiếp cấp chứng nhận/i,
    );
  });

  test("caps liability at 12 months of fees paid", () => {
    render(<TermsPage />);
    expect(screen.getByText(/12 tháng gần nhất/)).toBeInTheDocument();
  });

  test("cross-links to privacy page", () => {
    render(<TermsPage />);
    expect(
      screen.getByRole("link", { name: /Chính sách bảo mật/ }),
    ).toHaveAttribute("href", "/privacy");
  });
});
