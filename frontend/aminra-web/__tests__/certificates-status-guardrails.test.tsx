import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CertificatesPage from "@/app/certificates/page";

const authState = vi.hoisted(() => ({
  user: {
    role: "provider" as const,
    is_owner: true,
    company_name: "Halal CB Test",
  },
  token: "provider-token",
  isAuthenticated: true,
  loading: false,
}));
const routerReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace }),
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => authState,
}));

vi.mock("@/components/RevealOnScroll", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/certificates/ExpiryUrgency", () => ({
  default: () => null,
}));

vi.mock("@/lib/authedOpen", () => ({
  openAuthed: vi.fn(),
}));

const certificate = {
  id: "cert-1",
  cert_number: "HC-001",
  company_name: "Factory A",
  issue_date: "2026-01-01",
  expiry_date: "2027-01-01",
  days_remaining: 120,
  status: "active",
};

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function registryResponse() {
  return jsonResponse(200, {
    stats: { active: 1, expiring: 0, suspended: 0, revoked: 0 },
    certificates: [certificate],
  });
}

function findFetchCall(path: string, method: string): [RequestInfo | URL, RequestInit] {
  const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  const call = calls.find(
    ([url, init]) => String(url) === path && ((init?.method as string | undefined) || "GET") === method,
  );
  if (!call) throw new Error(`Missing fetch call: ${method} ${path}`);
  return call as [RequestInfo | URL, RequestInit];
}

describe("Certificates status write-flow guardrails", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/submissions/certificates/registry" && method === "GET") {
        return registryResponse();
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    }) as unknown as typeof fetch;
    vi.spyOn(window, "alert").mockImplementation(() => undefined);
  });

  it("PUTs status changes through the API client with bearer auth and JSON body", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/submissions/certificates/registry" && method === "GET") {
        return registryResponse();
      }
      if (String(url) === "/api/api/submissions/certificates/cert-1/status" && method === "PUT") {
        return jsonResponse(200, { ok: true });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    });

    render(<CertificatesPage />);

    await screen.findByText("Factory A");
    fireEvent.click(screen.getAllByRole("button", { name: "Đình chỉ" }).at(-1)!);
    await screen.findByRole("dialog");
    fireEvent.change(screen.getByPlaceholderText("Nhập lý do..."), {
      target: { value: "Audit finding pending CAPA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận đình chỉ" }));

    await waitFor(() => {
      expect(findFetchCall("/api/api/submissions/certificates/cert-1/status", "PUT")).toBeTruthy();
    });
    const [, init] = findFetchCall("/api/api/submissions/certificates/cert-1/status", "PUT");
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer provider-token");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init.body).toBe(JSON.stringify({ status: "suspended", reason: "Audit finding pending CAPA" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("surfaces FastAPI errors and keeps the confirmation modal open", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/submissions/certificates/registry" && method === "GET") {
        return registryResponse();
      }
      if (String(url) === "/api/api/submissions/certificates/cert-1/status" && method === "PUT") {
        return jsonResponse(403, { detail: "Bạn không có quyền: Cập nhật chứng nhận" });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    });

    render(<CertificatesPage />);

    await screen.findByText("Factory A");
    fireEvent.click(screen.getAllByRole("button", { name: "Thu hồi" }).at(-1)!);
    await screen.findByRole("dialog");
    fireEvent.change(screen.getByPlaceholderText("Nhập lý do..."), {
      target: { value: "Critical nonconformity" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận thu hồi" }));

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("Bạn không có quyền: Cập nhật chứng nhận");
    });
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Nhập lý do...")).toHaveValue("Critical nonconformity");
  });
});
