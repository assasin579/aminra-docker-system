import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ProcessPage from "@/app/supply-chain/process/page";

const authState = vi.hoisted(() => ({
  user: { role: "business" as const },
  token: "business-token",
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

vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ children }: { children: React.ReactNode }) => <div data-testid="react-flow">{children}</div>,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Panel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Handle: () => null,
  Position: { Top: "top", Bottom: "bottom" },
  useNodesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
  useEdgesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
  addEdge: (edge: unknown, edges: unknown[]) => [...edges, edge],
}));

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function findFetchCall(path: string, method: string): [RequestInfo | URL, RequestInit] {
  const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  const call = calls.find(([url, init]) => String(url) === path && ((init?.method as string | undefined) || "GET") === method);
  if (!call) throw new Error(`Missing fetch call: ${method} ${path}`);
  return call as [RequestInfo | URL, RequestInit];
}

describe("Supply-chain process create FE→BE contract", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/supply-chain/processes" && method === "GET") {
        return jsonResponse(200, { processes: [] });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    }) as unknown as typeof fetch;
    vi.spyOn(window, "alert").mockImplementation(() => undefined);
  });

  it("POSTs the modal name to the backend proxy with bearer auth and JSON content-type", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/supply-chain/processes" && method === "GET") {
        return jsonResponse(200, { processes: [] });
      }
      if (String(url) === "/api/api/supply-chain/processes" && method === "POST") {
        return jsonResponse(200, { id: "proc-1", message: "Đã tạo quy trình" });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    });

    render(<ProcessPage />);
    fireEvent.click(await screen.findByRole("button", { name: /tạo mới/i }));
    fireEvent.change(screen.getByPlaceholderText("Tên quy trình"), {
      target: { value: "Quy trình rang quế" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Tạo$/ }));

    await waitFor(() => {
      expect(findFetchCall("/api/api/supply-chain/processes", "POST")).toBeTruthy();
    });
    const [, createInit] = findFetchCall("/api/api/supply-chain/processes", "POST");
    const createHeaders = new Headers(createInit.headers);
    expect(createInit.method).toBe("POST");
    expect(createHeaders.get("Authorization")).toBe("Bearer business-token");
    expect(createHeaders.get("Content-Type")).toBe("application/json");
    expect(createInit.body).toBe(JSON.stringify({ name: "Quy trình rang quế" }));
    expect(await screen.findByText(/Đang sửa: Quy trình rang quế/)).toBeInTheDocument();
  });

  it("surfaces FastAPI save errors instead of showing a false success", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/supply-chain/processes" && method === "GET") {
        return jsonResponse(200, {
          processes: [
            {
              id: "proc-1",
              name: "Quy trình rang quế",
              description: null,
              flowchart: { nodes: [], edges: [] },
              version: 1,
              is_active: true,
              created_at: "",
              updated_at: "",
            },
          ],
        });
      }
      if (String(url) === "/api/api/supply-chain/processes/proc-1" && method === "PUT") {
        return jsonResponse(422, { detail: [{ loc: ["body", "name"], msg: "Field required", type: "missing" }] });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    });

    render(<ProcessPage />);
    fireEvent.click(await screen.findByText("Quy trình rang quế"));
    fireEvent.click(screen.getByRole("button", { name: /lưu quy trình/i }));

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith(expect.stringContaining("Field required"));
    });
    expect(screen.queryByRole("button", { name: /đã lưu/i })).not.toBeInTheDocument();
  });

  it("surfaces FastAPI create errors instead of failing silently", async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (String(url) === "/api/api/supply-chain/processes" && method === "GET") {
        return jsonResponse(200, { processes: [] });
      }
      if (String(url) === "/api/api/supply-chain/processes" && method === "POST") {
        return jsonResponse(403, { detail: "Bạn không có quyền: Chỉnh sửa dữ liệu" });
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${String(url)}` });
    });

    render(<ProcessPage />);
    fireEvent.click(await screen.findByRole("button", { name: /tạo mới/i }));
    fireEvent.change(screen.getByPlaceholderText("Tên quy trình"), {
      target: { value: "Quy trình lỗi quyền" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Tạo$/ }));

    await waitFor(() => {
      expect(window.alert).toHaveBeenCalledWith("Bạn không có quyền: Chỉnh sửa dữ liệu");
    });
    expect(screen.getByPlaceholderText("Tên quy trình")).toBeInTheDocument();
  });
});
