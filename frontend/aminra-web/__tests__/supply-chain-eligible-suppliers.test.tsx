import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MaterialsPage from "@/app/supply-chain/materials/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => ({
    user: { role: "business" },
    token: "test-token",
    isAuthenticated: true,
    loading: false,
  }),
}));

vi.mock("@/components/Modal", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/authedOpen", () => ({ openAuthed: vi.fn() }));

const ok = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });

const supplier = (id: string, name: string) => ({
  id,
  name,
  address: null,
  phone: null,
  email: null,
  contact_person: null,
  supplier_type: null,
  status: "pending",
  notes: null,
  material_count: 0,
  cert_count: 0,
  created_at: "2026-09-06T00:00:00Z",
});

describe("MaterialsPage eligible suppliers", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.startsWith("/api/api/supply-chain/materials")) {
          return Promise.resolve(ok({ materials: [] }));
        }
        if (url === "/api/api/supply-chain/certificate-risk-alerts?status=open") {
          return Promise.resolve(
            ok({
              alerts: [
                {
                  id: "alert-1",
                  supplier_id: "eligible-1",
                  supplier_name: "NCC đạt CB",
                  event_type: "revoked",
                  severity: "critical",
                  message: "Chứng nhận CB của NCC đạt CB đã revoked.",
                  status: "open",
                  created_at: "2026-09-06T00:00:00Z",
                },
              ],
            }),
          );
        }
        if (url === "/api/api/supply-chain/certificate-risk-alerts/alert-1") {
          return Promise.resolve(ok({ id: "alert-1", status: "acknowledged" }));
        }
        if (url === "/api/api/supply-chain/suppliers/eligible") {
          return Promise.resolve(ok({ suppliers: [supplier("eligible-1", "NCC đạt CB")] }));
        }
        if (url === "/api/api/supply-chain/suppliers/eligible?material_category=meat") {
          return Promise.resolve(ok({ suppliers: [supplier("meat-1", "NCC thịt đạt CB")] }));
        }
        if (url === "/api/api/supply-chain/suppliers/eligible?material_category=dairy") {
          return Promise.resolve(ok({ suppliers: [] }));
        }
        if (url === "/api/api/supply-chain/suppliers") {
          return Promise.resolve(
            ok({ suppliers: [supplier("legacy-1", "NCC chỉ upload hồ sơ")] }),
          );
        }
        return Promise.resolve(ok({}));
      }),
    );
  });

  it("fetches CB-eligible suppliers for the material dropdown and shows policy copy", async () => {
    render(<MaterialsPage />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/api/supply-chain/suppliers/eligible",
        expect.anything(),
      );
    });

    fireEvent.click(screen.getByRole("button", { name: /thêm nguyên liệu/i }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));

    expect(
      screen.getByText(/Chỉ NCC có chứng nhận CB đang hiệu lực/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "NCC đạt CB" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "NCC chỉ upload hồ sơ" })).not.toBeInTheDocument();
  });

  it("refetches eligible suppliers by material category and hides scope-mismatched suppliers", async () => {
    render(<MaterialsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /thêm nguyên liệu/i }));

    const categorySelect = screen.getAllByRole("combobox").find((select) => {
      const options = Array.from((select as HTMLSelectElement).options);
      return options[0]?.textContent === "Chọn..." && options.some((option) => option.value === "meat");
    }) as HTMLSelectElement;

    fireEvent.change(categorySelect, { target: { value: "meat" } });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/api/supply-chain/suppliers/eligible?material_category=meat",
        expect.anything(),
      );
    });
    expect(screen.getByRole("option", { name: "NCC thịt đạt CB" })).toBeInTheDocument();

    fireEvent.change(categorySelect, { target: { value: "dairy" } });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/api/supply-chain/suppliers/eligible?material_category=dairy",
        expect.anything(),
      );
    });
    expect(screen.queryByRole("option", { name: "NCC thịt đạt CB" })).not.toBeInTheDocument();
  });

  it("shows certificate risk alerts and lets buyer acknowledge them", async () => {
    render(<MaterialsPage />);

    expect(await screen.findByText("Cảnh báo chứng nhận NCC")).toBeInTheDocument();
    expect(screen.getByText(/Chứng nhận CB của NCC đạt CB đã revoked/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Đã xem" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/api/supply-chain/certificate-risk-alerts/alert-1",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ status: "acknowledged" }),
        }),
      );
    });
  });
});
