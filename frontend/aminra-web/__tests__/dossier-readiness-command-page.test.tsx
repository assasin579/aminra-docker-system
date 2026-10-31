import React, { Suspense } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DossierDetailPage from "@/app/dossiers/[id]/page";

const authState = vi.hoisted(() => ({
  token: "provider-token",
  isAuthenticated: true,
  loading: false,
  user: { role: "provider" } as { role: string; is_owner?: boolean },
}));
const routerReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace }),
}));

vi.mock("@/components/UserAuthContext", () => ({
  useUserAuth: () => authState,
}));

function jsonResponse(status: number, body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

const dossierFixture = {
  id: "dossier-1",
  title: "Hồ sơ nhà máy A",
  status: "in_progress",
  notes: null,
  standard_code: "HAS-23000",
  standard_name_vi: "Tiêu chuẩn Halal HAS 23000",
  doc_types: [
    { doc_type: "company_profile", required: true, display_order: 1 },
    { doc_type: "halal_policy", required: true, display_order: 2 },
    { doc_type: "has_manual", required: true, display_order: 3 },
  ],
  documents: [
    {
      id: "doc-1",
      doc_type: "company_profile",
      filename: "company.pdf",
      original_filename: "company.pdf",
      status: "approved",
      compliance_score: 98,
      version_number: 1,
      uploaded_at: "2026-09-01T00:00:00Z",
    },
    {
      id: "doc-2",
      doc_type: "halal_policy",
      filename: "policy.pdf",
      original_filename: "policy.pdf",
      status: "submitted",
      compliance_score: null,
      version_number: 1,
      uploaded_at: "2026-09-01T00:00:00Z",
    },
    {
      id: "doc-3",
      doc_type: "has_manual",
      filename: "manual.pdf",
      original_filename: "manual.pdf",
      status: "rejected",
      compliance_score: 41,
      version_number: 2,
      uploaded_at: "2026-09-01T00:00:00Z",
    },
  ],
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-02T00:00:00Z",
};

const readinessFixture = {
  state: "documents_rejected",
  readiness_percent: 40,
  certificate_issue_blocked: true,
  safe_public_trace_available: false,
  next_action: "replace_rejected_documents",
  next_actor_role: "business_owner",
  next_action_owner_role: "business",
  due_date: "2026-10-12",
  required_documents: ["company_profile", "halal_policy", "has_manual"],
  missing_required_documents: [
    { id: null, code: null, title: null, label: "Chính sách Halal", doc_type: "halal_policy", filename: null, reason: null, description: null, severity: null, deadline: null },
  ],
  unreviewed_documents: [
    { id: "doc-2", filename: "policy.pdf", doc_type: "halal_policy" },
  ],
  rejected_documents: [
    {
      id: "doc-3",
      filename: "manual.pdf",
      doc_type: "has_manual",
      reason: "Thiếu chữ ký phê duyệt",
    },
  ],
  open_ncrs: [
    {
      id: "ncr-1",
      code: "NCR-7",
      title: "CAPA vệ sinh chưa đóng",
      severity: "major",
    },
  ],
  blocking_ncrs: [
    {
      id: "ncr-1",
      code: "NCR-7",
      title: "CAPA vệ sinh chưa đóng",
      severity: "major",
      description: "CAPA vệ sinh chưa đóng",
      deadline: "2026-10-12",
    },
  ],
  certification_decision: null,
  certificate: null,
  blocking_reasons: [
    { code: "open_ncr", title: "Certificate issue blocked until CAPA closure" },
  ],
};

function renderPage() {
  const params = Promise.resolve({ id: "dossier-1" }) as Promise<{ id: string }> & {
    status?: string;
    value?: { id: string };
  };
  params.status = "fulfilled";
  params.value = { id: "dossier-1" };

  return render(
    <Suspense fallback={<div>Loading suspense...</div>}>
      <DossierDetailPage params={params} />
    </Suspense>,
  );
}

function findFetchCall(path: string): [RequestInfo | URL, RequestInit | undefined] {
  const calls = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
  const call = calls.find(([url]) => String(url) === path);
  if (!call) throw new Error(`Missing fetch call: GET ${path}`);
  return call as [RequestInfo | URL, RequestInit | undefined];
}

describe("Dossier detail certification readiness command panel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user = { role: "provider" };
    global.fetch = vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
      const path = String(url);
      const method = init?.method || "GET";
      if (path === "/api/dossiers/dossier-1" && method === "GET") {
        return jsonResponse(200, dossierFixture);
      }
      if (path === "/api/dossiers/dossier-1/readiness" && method === "GET") {
        return jsonResponse(200, readinessFixture);
      }
      return jsonResponse(500, { detail: `Unhandled mock: ${method} ${path}` });
    }) as unknown as typeof fetch;
  });

  it.each([
    { owner: true, status: "in_progress", documents: dossierFixture.documents, visible: true },
    { owner: false, status: "in_progress", documents: dossierFixture.documents, visible: false },
    { owner: true, status: "cert_issued", documents: dossierFixture.documents, visible: false },
    { owner: true, status: "in_progress", documents: [], visible: false },
  ])("handoff uses the exact dossier and owner capability: $owner/$status/$visible", async ({ owner, status, documents, visible }) => {
    authState.user = { role: "business", is_owner: owner };
    vi.mocked(fetch).mockImplementation((url) => String(url).endsWith("/readiness")
      ? jsonResponse(200, readinessFixture)
      : String(url).endsWith("/attachable-documents")
        ? jsonResponse(200, [])
        : jsonResponse(200, { ...dossierFixture, status, documents, requirements_binding_status: "bound" }));
    renderPage();
    await screen.findByText("Hồ sơ nhà máy A");
    if (visible) expect(screen.getByTestId("dossier-submit-cta")).toHaveAttribute("href", "/submissions?dossier_id=dossier-1");
    else expect(screen.queryByTestId("dossier-submit-cta")).not.toBeInTheDocument();
  });

  it("fetches source-of-truth readiness and renders blockers instead of trusting uploaded document count", async () => {
    renderPage();

    await screen.findByText("Hồ sơ nhà máy A");

    await waitFor(() => {
      expect(findFetchCall("/api/dossiers/dossier-1")).toBeTruthy();
      expect(findFetchCall("/api/dossiers/dossier-1/readiness")).toBeTruthy();
    });

    for (const path of ["/api/dossiers/dossier-1", "/api/dossiers/dossier-1/readiness"]) {
      const [, init] = findFetchCall(path);
      const headers = new Headers(init?.headers);
      expect(headers.get("Authorization")).toBe("Bearer provider-token");
    }

    expect(screen.getByText("Mức sẵn sàng chứng nhận")).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === "40%")).toBeInTheDocument();
    expect(screen.getByText("Thay thế tài liệu bị từ chối")).toBeInTheDocument();
    expect(screen.getByText("Doanh nghiệp")).toBeInTheDocument();
    expect(screen.getByTestId("dossier-readiness-state")).toHaveTextContent("Cần sửa tài liệu bị từ chối");
    expect(screen.getByTestId("readiness-due-date")).toHaveTextContent("12/10/2026");
    expect(screen.getAllByText(/Chính sách Halal/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Thiếu chữ ký phê duyệt/)).toBeInTheDocument();
    expect(screen.getByText(/NCR-7/)).toBeInTheDocument();
    expect(screen.getByTestId("readiness-recovery-cta")).toHaveTextContent("Thay tài liệu bị từ chối");
    expect(screen.getByText(/CAPA vệ sinh chưa đóng/)).toBeInTheDocument();
    expect(screen.getByText(/Chưa thể cấp chứng nhận/)).toBeInTheDocument();
    expect(screen.getByText(/Chưa có trang truy xuất công khai/)).toBeInTheDocument();

    expect(screen.getByText((_, node) => node?.textContent === "3/3 loại đã có tài liệu")).toBeInTheDocument();
    expect(screen.getByText((_, node) => node?.textContent === "40%")).toBeInTheDocument();
    expect(screen.getByText(/Cần đóng điểm không phù hợp trước khi ra quyết định/)).toBeInTheDocument();
  });

  it("fails closed on a malformed readiness response instead of crashing the page", async () => {
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url) === "/api/dossiers/dossier-1/readiness" && (init?.method || "GET") === "GET") {
        return jsonResponse(200, { readiness_percent: 75, certificate_issue_blocked: false });
      }
      return jsonResponse(200, dossierFixture);
    });

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được trạng thái sẵn sàng");
    expect(screen.queryByTestId("certification-readiness-panel")).not.toBeInTheDocument();
  });

  it("fails closed when readiness arrays contain malformed items", async () => {
    const malformedReadiness = { ...readinessFixture, open_ncrs: [null] };
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url) === "/api/dossiers/dossier-1/readiness" && (init?.method || "GET") === "GET") {
        return jsonResponse(200, malformedReadiness);
      }
      return jsonResponse(200, dossierFixture);
    });

    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được trạng thái sẵn sàng");
    expect(screen.queryByTestId("certification-readiness-panel")).not.toBeInTheDocument();
  });

  it("shows minor NCRs as informational, not as decision blockers", async () => {
    const minorReadiness = {
      ...readinessFixture,
      open_ncrs: [{ id: "ncr-minor", severity: "minor", description: "Ghi chú cải tiến" }],
      blocking_ncrs: [],
    };
    (global.fetch as unknown as ReturnType<typeof vi.fn>).mockImplementation((url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url) === "/api/dossiers/dossier-1/readiness" && (init?.method || "GET") === "GET") {
        return jsonResponse(200, minorReadiness);
      }
      return jsonResponse(200, dossierFixture);
    });

    renderPage();

    await screen.findByText("Hồ sơ nhà máy A");
    expect(screen.getByText(/1 NCR mức nhẹ đang mở; hiện không chặn quyết định/)).toBeInTheDocument();
    expect(screen.queryByText("NCR/CAPA đang chặn quyết định")).not.toBeInTheDocument();
  });
  it("accepts real API nullable optional fields and keeps the owner attachment controls available", async () => {
    authState.user = { role: "business", is_owner: true };
    const actualShape = { ...readinessFixture, state: "requirements_pending", readiness_percent: 25,
      unreviewed_documents: [], rejected_documents: [], open_ncrs: [], blocking_ncrs: [],
      blocking_reasons: [{ id: null, code: "missing_required_document", title: null, label: null,
        doc_type: "has_manual", filename: null, reason: null, description: null, severity: null, deadline: null }],
    };
    vi.mocked(fetch).mockImplementation((url) => jsonResponse(200, String(url).endsWith("/readiness")
      ? actualShape : { ...dossierFixture, requirements_binding_status: "bound" }));
    renderPage();
    expect(await screen.findAllByRole("button", { name: "Đính kèm tài liệu" })).toHaveLength(3);
    expect(screen.getByLabelText("Sẵn sàng 25 phần trăm")).toBeInTheDocument();
    expect(screen.queryByText("Không tải được trạng thái sẵn sàng")).not.toBeInTheDocument();
  });
});


describe("Dossier editing capability and lifecycle UX", () => {
  it.each([
    ["business",true,"in_progress",true],
    ["business",false,"in_progress",false],
    ["provider",true,"in_progress",false],
    ["business",true,"cancelled",false],
    ["business",true,"cert_issued",false],
  ] as const)("%s owner=%s status=%s has editable documents=%s", async (role,owner,status,editable) => {
    authState.user={role,is_owner:owner};
    global.fetch=vi.fn((url)=>String(url).endsWith("/readiness")
      ?jsonResponse(200,{...readinessFixture,state:"documents_ready_to_submit",next_action:"submit_dossier_to_cb",next_actor_role:"business",requirement_slots:[]})
      :String(url).endsWith("/attachable-documents")?jsonResponse(200,{items:[]})
      :jsonResponse(200,{...dossierFixture,status,requirements_binding_status:"bound"}));
    renderPage();await screen.findByText("Hồ sơ nhà máy A");
    expect(screen.queryAllByRole("button",{name:"Đính kèm tài liệu"})).toHaveLength(editable?3:0);
    expect(screen.queryByTestId("dossier-create-doc-cta")!==null).toBe(editable);
    expect(screen.queryByRole("form",{name:"Bổ sung tài liệu hồ sơ"})).not.toBeInTheDocument();
    if(editable){expect(screen.getByTestId("dossier-readiness-state")).toHaveTextContent("chưa gửi đơn vị chứng nhận");expect(screen.getByText("Gửi hồ sơ cho đơn vị chứng nhận")).toBeInTheDocument();}
    if(["cancelled","cert_issued"].includes(status)){expect(screen.getByText("Hồ sơ đã đóng; bạn có thể xem lại lịch sử")).toBeInTheDocument();}
  });

  it("a submitted dossier links to tracking rather than creating another submission", async () => {
    authState.user={role:"business",is_owner:true};
    global.fetch=vi.fn((url)=>String(url).endsWith("/readiness")?jsonResponse(200,{...readinessFixture,requirement_slots:[{submission_id:"existing-submission"}]})
      :String(url).endsWith("/attachable-documents")?jsonResponse(200,{items:[]})
      :jsonResponse(200,{...dossierFixture,requirements_binding_status:"bound"}));
    renderPage();await screen.findByText("Hồ sơ nhà máy A");
    expect(screen.queryByTestId("dossier-submit-cta")).not.toBeInTheDocument();
    expect(screen.getByRole("link",{name:"Xem hồ sơ đã gửi"})).toHaveAttribute("href","/submissions");
  });
});
