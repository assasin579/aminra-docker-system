/**
 * Unit tests — "Gửi hồ sơ mới" modal (migrated từ documents → submissions page).
 *
 * Coverage:
 * - Button chỉ render cho business user, không render cho provider
 * - openSubmitModal fetch providers + docs đồng thời (Promise.all)
 * - selectedDocs được pre-select toàn bộ docs trả về
 * - Empty state khi không có docs → hiện link "/documents"
 * - handleSubmit gửi đúng payload (provider_id, document_ids[], notes)
 * - handleSubmit gọi fetchSubs và đóng modal khi thành công
 * - handleSubmit hiện alert khi API lỗi, không đóng modal
 * - Button submit disabled khi chưa chọn provider hoặc không có doc nào được tick
 */
import { describe, test, expect, vi, beforeEach, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useUserAuth } from "@/components/UserAuthContext";
import SubmissionsPage from "@/app/submissions/page";

// ── Next.js stubs ──────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
}));

// ── Auth context ────────────────────────────────────────────────────────────

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: vi.fn(),
}));

const mockUseUserAuth = useUserAuth as ReturnType<typeof vi.fn>;

const BIZ_USER = {
  role: "business",
  is_owner: true,
  ihc_role: null,
  permissions: {},
};

const PROV_USER = {
  role: "provider",
  is_owner: true,
  ihc_role: null,
  permissions: {},
};

// ── Heavy sub-component stubs ───────────────────────────────────────────────

vi.mock("@/components/submissions/RevisionPanel", () => ({
  default: () => null,
}));
vi.mock("@/components/submissions/SlaBadge", () => ({
  default: () => null,
}));
vi.mock("@/components/Modal", () => ({
  default: ({ children, onClose }: { children: React.ReactNode; onClose?: () => void }) => (
    <div data-testid="modal" onClick={onClose}>
      {children}
    </div>
  ),
}));
vi.mock("@/lib/authedOpen", () => ({ openAuthed: vi.fn() }));
vi.mock("@/lib/apiError", () => ({
  parseApiError: (_: unknown, fallback: string) => fallback,
}));

// ── Helpers ────────────────────────────────────────────────────────────────

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

const emptySubs = () => respond(200, { submissions: [] });
const emptyAuditors = () => respond(200, { auditors: [] });

function mockBizAuth() {
  mockUseUserAuth.mockReturnValue({
    user: BIZ_USER,
    token: "biz-jwt",
    isAuthenticated: true,
    loading: false,
  });
}

function mockProvAuth() {
  mockUseUserAuth.mockReturnValue({
    user: PROV_USER,
    token: "prov-jwt",
    isAuthenticated: true,
    loading: false,
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  vi.stubGlobal("alert", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ── Button visibility ───────────────────────────────────────────────────────

describe("Vị trí button Gửi hồ sơ mới", () => {
  test("business user thấy button Gửi hồ sơ mới trong trang submissions", async () => {
    mockBizAuth();
    (fetch as ReturnType<typeof vi.fn>).mockImplementation(() => emptySubs());

    render(<SubmissionsPage />);

    expect(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    ).toBeInTheDocument();
  });

  test("provider user KHÔNG thấy button Gửi hồ sơ mới", async () => {
    mockProvAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { submissions: [] })) // fetchSubs
      .mockResolvedValueOnce(respond(200, { auditors: [] }));  // fetchAuditors

    render(<SubmissionsPage />);

    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /Gửi hồ sơ mới/i }),
      ).not.toBeInTheDocument();
    });
  });
});

// ── openSubmitModal ─────────────────────────────────────────────────────────

describe("openSubmitModal", () => {
  test("fetch providers và docs đồng thời khi click button", async () => {
    mockBizAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())             // fetchSubs on mount
      .mockResolvedValueOnce(respond(200, { providers: [] }))   // providers
      .mockResolvedValueOnce(respond(200, { documents: [] }));  // docs

    render(<SubmissionsPage />);

    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );

    await waitFor(() => {
      const calls = (fetchMock as ReturnType<typeof vi.fn>).mock.calls.map(
        (c: unknown[]) => c[0],
      );
      expect(calls).toContain("/api/api/submissions/providers");
      expect(calls.some((u: unknown) => typeof u === "string" && u.includes("/api/api/documents"))).toBe(true);
    });
  });

  test("modal mở sau khi fetch xong", async () => {
    mockBizAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())
      .mockResolvedValueOnce(respond(200, { providers: [] }))
      .mockResolvedValueOnce(respond(200, { documents: [] }));

    render(<SubmissionsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );

    expect(await screen.findByTestId("modal")).toBeInTheDocument();
    expect(
      screen.getByText(/Gửi hồ sơ đến tổ chức chứng nhận/i),
    ).toBeInTheDocument();
  });

  test("selectedDocs được pre-select toàn bộ docs trả về", async () => {
    mockBizAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())
      .mockResolvedValueOnce(respond(200, { providers: [] }))
      .mockResolvedValueOnce(
        respond(200, {
          documents: [
            { id: "d1", original_filename: "policy.pdf", doc_type_label: "Halal Policy" },
            { id: "d2", original_filename: "manual.docx", doc_type_label: "HAS Manual" },
          ],
        }),
      );

    render(<SubmissionsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );

    await waitFor(() => {
      const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
      expect(checkboxes).toHaveLength(2);
      checkboxes.forEach((cb) => expect(cb).toBeChecked());
    });

    // Counter label phản ánh đúng
    expect(screen.getByText(/2\/2/)).toBeInTheDocument();
  });

  test("empty state khi không có docs — hiện link Upload tài liệu", async () => {
    mockBizAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())
      .mockResolvedValueOnce(respond(200, { providers: [] }))
      .mockResolvedValueOnce(respond(200, { documents: [] }));

    render(<SubmissionsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );

    expect(
      await screen.findByRole("link", { name: /Upload tài liệu/i }),
    ).toHaveAttribute("href", "/documents");
  });
});

// ── handleSubmit ────────────────────────────────────────────────────────────

describe("handleSubmit", () => {
  const PROVIDERS = [
    { id: "prov-1", company_name: "HALCERT Vietnam", email: "halcert@vn" },
  ];
  const DOCS = [
    { id: "doc-1", original_filename: "policy.pdf", doc_type_label: "Halal Policy" },
  ];

  async function openModalWithData() {
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())
      .mockResolvedValueOnce(respond(200, { providers: PROVIDERS }))
      .mockResolvedValueOnce(respond(200, { documents: DOCS }));

    render(<SubmissionsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );
    await screen.findByText("HALCERT Vietnam");
    return fetchMock;
  }

  test("button Gửi X tài liệu disabled khi chưa chọn provider", async () => {
    mockBizAuth();
    await openModalWithData();

    const submitBtn = screen.getByRole("button", {
      name: /Gửi 1 tài liệu/i,
    });
    expect(submitBtn).toBeDisabled();
  });

  test("gửi đúng payload khi chọn đủ provider + docs", async () => {
    mockBizAuth();
    const fetchMock = await openModalWithData();
    fetchMock
      .mockResolvedValueOnce(respond(200, { message: "OK" })) // submit
      .mockResolvedValueOnce(emptySubs());                     // fetchSubs refresh

    // Chọn provider
    fireEvent.click(screen.getByText("HALCERT Vietnam"));

    // Thêm ghi chú
    fireEvent.change(
      screen.getByPlaceholderText(/Thông tin thêm cho tổ chức/i),
      { target: { value: "Hồ sơ lần 1" } },
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Gửi 1 tài liệu/i }),
    );

    await waitFor(() => {
      const submitCall = fetchMock.mock.calls.find(
        (c: unknown[]) => typeof c[0] === "string" && c[0].includes("/submissions/submit"),
      );
      expect(submitCall).toBeDefined();
      const body = JSON.parse((submitCall![1] as { body: string }).body);
      expect(body).toEqual({
        provider_id: "prov-1",
        document_ids: ["doc-1"],
        notes: "Hồ sơ lần 1",
      });
    });
  });

  test("modal đóng và fetchSubs được gọi sau khi submit thành công", async () => {
    mockBizAuth();
    const fetchMock = await openModalWithData();
    fetchMock
      .mockResolvedValueOnce(respond(200, { message: "OK" }))
      .mockResolvedValueOnce(emptySubs());

    fireEvent.click(screen.getByText("HALCERT Vietnam"));
    fireEvent.click(screen.getByRole("button", { name: /Gửi 1 tài liệu/i }));

    await waitFor(() => {
      expect(screen.queryByTestId("modal")).not.toBeInTheDocument();
    });

    // fetchSubs gọi lần 2 (lần 1 là mount)
    const subsCalls = fetchMock.mock.calls.filter(
      (c: unknown[]) => typeof c[0] === "string" && c[0].includes("my-submissions"),
    );
    expect(subsCalls.length).toBeGreaterThanOrEqual(2);
  });

  test("hiện alert và giữ modal khi API trả lỗi", async () => {
    mockBizAuth();
    const fetchMock = await openModalWithData();
    fetchMock.mockResolvedValueOnce(
      respond(400, { detail: "Provider không tồn tại" }),
    );

    fireEvent.click(screen.getByText("HALCERT Vietnam"));
    fireEvent.click(screen.getByRole("button", { name: /Gửi 1 tài liệu/i }));

    await waitFor(() => {
      expect(vi.mocked(alert)).toHaveBeenCalledWith("Provider không tồn tại");
    });

    // Modal vẫn còn
    expect(screen.getByTestId("modal")).toBeInTheDocument();
  });

  test("uncheck một doc → counter giảm → button label cập nhật", async () => {
    mockBizAuth();
    const fetchMock = fetch as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(emptySubs())
      .mockResolvedValueOnce(respond(200, { providers: PROVIDERS }))
      .mockResolvedValueOnce(
        respond(200, {
          documents: [
            ...DOCS,
            { id: "doc-2", original_filename: "sop.docx", doc_type_label: "SOP" },
          ],
        }),
      );

    render(<SubmissionsPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /Gửi hồ sơ mới/i }),
    );
    await screen.findByText("HALCERT Vietnam");

    // Uncheck doc đầu tiên
    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    fireEvent.click(checkboxes[0]);

    expect(screen.getByText(/1\/2/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Gửi 1 tài liệu/i }),
    ).toBeInTheDocument();
  });
});
