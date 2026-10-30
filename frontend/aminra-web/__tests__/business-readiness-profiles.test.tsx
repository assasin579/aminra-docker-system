import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BusinessReadinessProfiles from "../components/dashboard/BusinessReadinessProfiles";

function payload(overrides: Record<string, unknown> = {}) {
  return { state: "ready", as_of: "2026-10-30T12:00:00Z", page: 1, page_size: 20, total_dossiers: 1,
    profiles: [{ id: "profile-private-uuid", code: "A", name_vi: "Tiêu chuẩn A", dossiers: [{ id: "dossier-private-uuid", title: "Hồ sơ A", requirements_version_number: 2, requirements_version_id: "version-private-uuid", requirements_binding_status: "bound", readiness: { state: "documents_in_review", readiness_percent: 25, requirements_version_id: "version-private-uuid", requirements_binding_status: "bound", next_actor_role: "reviewer", requirement_slots: [
      { doc_type: "policy", required: true, state: "approved", evidence_document_id: "evidence-private-uuid", evidence_version: 2, submitted_round: 3 },
      { doc_type: "manual", required: true, state: "pending_review" },
      { doc_type: "label", required: false, state: "optional_not_submitted" },
    ] } }] }], ...overrides };
}
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
beforeEach(() => vi.stubGlobal("fetch", vi.fn()));

describe("Business dossier readiness", () => {
  it("shows accessible loading and first-use action", async () => {
    let resolve!: (r: Response) => void;
    vi.mocked(fetch).mockReturnValue(new Promise(r => { resolve = r; }));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    expect(screen.getByRole("status")).toHaveTextContent("Đang tải");
    resolve(ok(payload({ state: "first_use", total_dossiers: 0, profiles: [] })));
    expect(await screen.findByRole("link", { name: "Tạo hồ sơ" })).toHaveAttribute("href", "/dossiers/new");
  });
  it("shows exact server readiness and human-review state without exposing internal IDs", async () => {
    vi.mocked(fetch).mockResolvedValue(ok(payload()));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    const region = within(await screen.findByRole("region", { name: "Hồ sơ A" }));
    expect(region.getByText("Mức sẵn sàng: 25%")).toBeInTheDocument();
    expect(region.getByText("Đã được duyệt")).toBeInTheDocument();
    expect(region.getByText("Chờ đánh giá")).toBeInTheDocument();
    expect(region.getByText(/Phiên bản yêu cầu 2/)).toBeInTheDocument();
    expect(region.getByText(/Tài liệu phiên bản 2/)).toBeInTheDocument();
    expect(region.getByText(/Vòng đánh giá 3/)).toBeInTheDocument();
    expect(screen.queryByText(/private-uuid/)).not.toBeInTheDocument();
    expect(region.getByRole("link", { name: "Xem hồ sơ" })).toHaveAttribute("href", "/dossiers/dossier-private-uuid");
  });
  it.each(["unknown", "unconfigured"])("does not fabricate a percentage for %s requirements", async binding => {
    const p = payload(); const d = p.profiles[0].dossiers[0];
    d.requirements_binding_status = binding; d.readiness.requirements_binding_status = binding;
    d.readiness.state = "requirements_" + binding; d.readiness.readiness_percent = 99;
    vi.mocked(fetch).mockResolvedValue(ok(p));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    const r = within(await screen.findByRole("region", { name: "Hồ sơ A" }));
    expect(r.queryByText(/Mức sẵn sàng:/)).not.toBeInTheDocument();
    expect(r.getByText(binding === "unknown" ? /Chưa xác định bộ yêu cầu/ : /Chờ công bố yêu cầu/)).toBeInTheDocument();
  });
  it.each(["requirements_empty", "requirements_no_required_slots"])("treats %s as N/A", async state => {
    const p = payload(); p.profiles[0].dossiers[0].readiness.state = state;
    vi.mocked(fetch).mockResolvedValue(ok(p));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    const r = within(await screen.findByRole("region", { name: "Hồ sơ A" }));
    expect(r.getByText(/chưa áp dụng tỷ lệ/)).toBeInTheDocument();
    expect(r.queryByText(/Mức sẵn sàng:/)).not.toBeInTheDocument();
  });
  it("keeps different standards and required slot populations separate", async () => {
    const p = payload({ total_dossiers: 2 }); const second = structuredClone(p.profiles[0]);
    second.id = "profile-b"; second.name_vi = "Tiêu chuẩn B"; second.dossiers[0].id = "b"; second.dossiers[0].title = "Hồ sơ B";
    second.dossiers[0].readiness.readiness_percent = 50; second.dossiers[0].readiness.requirement_slots = [{ doc_type: "other", required: true, state: "pending_review" }];
    p.profiles.push(second); vi.mocked(fetch).mockResolvedValue(ok(p));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    expect(within(await screen.findByRole("region", { name: "Hồ sơ A" })).getByText("Mức sẵn sàng: 25%")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Hồ sơ B" })).getByText("Mức sẵn sàng: 50%")).toBeInTheDocument();
    expect(screen.queryByText(/\/13|0\/13/)).not.toBeInTheDocument();
  });
  it("uses business action only when the server assigns that actor", async () => {
    const p = payload(); const d = p.profiles[0].dossiers[0].readiness; d.next_actor_role = "business";
    Object.assign(d, { next_action: "replace_rejected_documents" });
    vi.mocked(fetch).mockResolvedValue(ok(p)); render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    expect(await screen.findByRole("link", { name: "Sửa tài liệu bị trả lại" })).toBeInTheDocument();
  });
  it("clears tenant A data before a delayed tenant B request completes", async () => {
    let resolveB!: (r: Response) => void;
    vi.mocked(fetch).mockResolvedValueOnce(ok(payload())).mockReturnValueOnce(new Promise(r => { resolveB = r; }));
    const { rerender } = render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    await screen.findByRole("region", { name: "Hồ sơ A" });
    rerender(<BusinessReadinessProfiles token="a" contextKey="tenant-b" />);
    await waitFor(() => expect(screen.queryByRole("region", { name: "Hồ sơ A" })).not.toBeInTheDocument());
    resolveB({ ok: false, status: 403 } as Response);
    expect(await screen.findByRole("alert")).toHaveTextContent("không có quyền");
  });
  it("shows retry instead of misleading empty state on request failure", async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(ok(payload()));
    render(<BusinessReadinessProfiles token="a" contextKey="tenant-a" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Không tải được");
    fireEvent.click(screen.getByRole("button", { name: "Tải lại" }));
    expect(await screen.findByRole("region", { name: "Hồ sơ A" })).toBeInTheDocument();
  });
});
