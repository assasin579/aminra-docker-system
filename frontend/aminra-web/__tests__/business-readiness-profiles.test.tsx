import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BusinessReadinessProfiles from "../components/dashboard/BusinessReadinessProfiles";

const payload = (overrides: Record<string, unknown> = {}) => ({
  schema_version: "1.0", state: "ready", as_of: "2026-10-20T12:00:00Z", page: 1, page_size: 20, total_dossiers: 3,
  profiles: [
    { id: "p1", code: "A", name_vi: "Profile A", dossiers: [{ id: "d1", title: "Dossier One", status: "in_progress", requirements_version_id: "v1", requirements_binding_status: "bound", updated_at: "2026-10-19", readiness: { state: "requirements_pending", readiness_percent: 50, requirements_binding_status: "bound", requirements_version_id: "v1", next_action: "upload_required_documents", next_actor_role: "business", requirement_slots: [{ doc_type: "manual", required: true, display_order: 1, requirements_version_id: "v1", submission_id: null, submitted_round: null, evidence_document_id: null, evidence_version: null, state: "missing_required" }, { doc_type: "label", required: false, display_order: 2, requirements_version_id: "v1", submission_id: "s1", submitted_round: 1, evidence_document_id: "e1", evidence_version: 3, state: "pending_review" }] } }] },
    { id: "p2", code: "B", name_vi: "Profile B", dossiers: [{ id: "d2", title: "Dossier Two", status: "in_progress", requirements_version_id: "v2", requirements_binding_status: "bound", updated_at: "2026-10-18", readiness: { state: "requirements_pending", readiness_percent: 20, requirements_binding_status: "bound", requirements_version_id: "v2", next_action: "review", next_actor_role: "certification_body", requirement_slots: [{ doc_type: "policy", required: true, state: "pending_review", evidence_document_id: "e2", evidence_version: 1 }] } }] },
    { id: null, code: null, name_vi: null, dossiers: [{ id: "d3", title: "Legacy dossier", status: "in_progress", requirements_version_id: null, requirements_binding_status: "unknown", updated_at: "2026-10-17", readiness: { state: "requirements_unknown", readiness_percent: 99, requirements_binding_status: "unknown", requirements_version_id: null, next_action: "resolve_requirements_binding", next_actor_role: "platform_admin", requirement_slots: [] } }] },
  ], ...overrides,
});

beforeEach(() => { vi.stubGlobal("fetch", vi.fn()); });
const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body });

describe("BusinessReadinessProfiles", () => {
  it("shows accessible loading state", () => {
    vi.mocked(fetch).mockReturnValue(new Promise(() => {}) as Promise<Response>);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
  });
  it("distinguishes first use from forbidden", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(ok(payload({ state: "first_use", total_dossiers: 0, profiles: [] })) as Response);
    const { rerender } = render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findByRole("link", { name: /create dossier/i })).toHaveAttribute("href", "/dossiers/new");
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 403 } as Response);
    rerender(<BusinessReadinessProfiles token="t2" contextKey="actor-b:org-b:business:active:owner:upload:industry-b" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/not authorized|forbidden/i);
    expect(screen.queryByText(/no dossiers/i)).not.toBeInTheDocument();
  });
  it("renders isolated profiles, versions, exact slot states, evidence, and actor-specific actions", async () => {
    vi.mocked(fetch).mockResolvedValue(ok(payload()) as Response);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findByText("Profile A")).toBeInTheDocument();
    expect(screen.getByText("Profile B")).toBeInTheDocument();
    expect(screen.getByText(/requirements version: v1/)).toBeInTheDocument(); expect(screen.getByText(/requirements version: v2/)).toBeInTheDocument();
    expect(screen.getByText("missing_required")).toBeInTheDocument(); expect(screen.getAllByText("pending_review")).toHaveLength(2);
    expect(screen.getByText(/e1/)).toBeInTheDocument(); expect(screen.getByText(/version 3/i)).toBeInTheDocument();
    expect(screen.getByText(/Readiness:.*50/)).toBeInTheDocument(); expect(screen.queryByText(/Readiness:.*99/)).not.toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Legacy dossier" })).getByText(/UNKNOWN \(legacy\/unbound\)/)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Dossier Two" })).getByRole("link", { name: /open dossier/i })).toHaveAttribute("href", "/dossiers/d2"); expect(within(screen.getByRole("region", { name: "Dossier One" })).getByRole("link", { name: /upload required documents/i })).toHaveAttribute("href", "/dossiers/d1");
    expect(screen.getAllByText(/waiting/i)).toHaveLength(2);
    expect(screen.getByText(/page 1/i)).toBeInTheDocument();
  });
  it("shows empty published requirements without a fabricated percentage", async () => {
    const p = payload();
    const profiles = p.profiles as Array<{ dossiers: Array<{ readiness: Record<string, unknown> }> }>;
    profiles[0].dossiers[0].readiness = { state: "requirements_empty", readiness_percent: null, requirements_binding_status: "bound", requirements_version_id: "v1", next_action: "configure_requirement_slots", next_actor_role: "platform_admin", requirement_slots: [] };
    vi.mocked(fetch).mockResolvedValue(ok(p) as Response);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    const dossier = within(await screen.findByRole("region", { name: "Dossier One" }));
    expect(dossier.getByText(/published requirements have no slots/i)).toBeInTheDocument();
    expect(dossier.queryByText(/Readiness:/)).not.toBeInTheDocument();
    expect(dossier.getByText(/requirements version: v1/i)).toBeInTheDocument();
  });
  it("renders server readiness for exact required slots and round-scoped human approval", async () => {
    const p = payload();
    const profiles = p.profiles as Array<{ dossiers: Array<{ readiness: Record<string, unknown> }> }>;
    profiles[0].dossiers[0].readiness = { state: "documents_in_review", readiness_percent: 25, requirements_binding_status: "bound", requirements_version_id: "version-pinned", next_action: "review_uploaded_documents", next_actor_role: "reviewer", requirement_slots: [
      { doc_type: "policy", required: true, state: "pending_review", evidence_document_id: "doc-ai-only", evidence_version: 3, requirements_version_id: "version-pinned", submission_id: "submission-current", submitted_round: 4 },
      { doc_type: "manual", required: true, state: "approved", evidence_document_id: "doc-reviewed", evidence_version: 2, requirements_version_id: "version-pinned", submission_id: "submission-current", submitted_round: 4 },
      { doc_type: "optional", required: false, state: "optional_not_submitted", requirements_version_id: "version-pinned", submission_id: "submission-current", submitted_round: 4 },
    ] };
    vi.mocked(fetch).mockResolvedValue(ok(p) as Response);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    const dossier = within(await screen.findByRole("region", { name: "Dossier One" }));
    expect(dossier.getByText("Readiness: 25%")).toBeInTheDocument();
    expect(dossier.getByText("pending_review")).toBeInTheDocument();
    expect(dossier.getByText("approved")).toBeInTheDocument();
    expect(dossier.getByText(/doc-ai-only, version 3/)).toBeInTheDocument();
    expect(dossier.getAllByText(/submission-current, round 4/)).toHaveLength(3);
  });
  it("does not treat AI-compliant evidence as approved", async () => {
    const p = payload();
    const profiles = p.profiles as Array<{ dossiers: Array<{ readiness: { requirement_slots: Array<Record<string, unknown>> } }> }>;
    profiles[0].dossiers[0].readiness.requirement_slots[1] = { ...profiles[0].dossiers[0].readiness.requirement_slots[1], state: "pending_review", ai_status: "compliant" };
    vi.mocked(fetch).mockResolvedValue(ok(p) as Response);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findAllByText("pending_review")).toHaveLength(2); expect(screen.queryByText("approved")).not.toBeInTheDocument();
  });
  it("does not fabricate a readiness percentage or block an optional-only dossier", async () => {
    const p = payload();
    const profiles = p.profiles as Array<{ dossiers: Array<{ readiness: Record<string, unknown> }> }>;
    profiles[0].dossiers[0].readiness = { state: "requirements_no_required_slots", readiness_percent: null, requirements_binding_status: "bound", requirements_version_id: "v1", next_action: "configure_required_slots", next_actor_role: "platform_admin", requirement_slots: [{ doc_type: "optional-record", required: false, state: "missing_optional" }] };
    vi.mocked(fetch).mockResolvedValue(ok(p) as Response);
    render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findByText(/percentage is not applicable/i)).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Dossier One" })).queryByText(/Readiness:/)).not.toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Dossier One" })).getByRole("link", { name: /open dossier/i })).toHaveAttribute("href", "/dossiers/d1");
    expect(screen.queryByRole("link", { name: /upload required documents/i })).not.toBeInTheDocument();
  });
  it("shows safe error, and retains data as partial on refresh failure only in same token scope", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(ok(payload()) as Response).mockRejectedValueOnce(new Error("private tenant detail"));
    const { rerender } = render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findByText("Profile A")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
    expect(await screen.findByText(/stale|partial/i)).toBeInTheDocument();
    expect(screen.queryByText(/private tenant detail/)).not.toBeInTheDocument();
    vi.mocked(fetch).mockRejectedValueOnce(new Error("network"));
    rerender(<BusinessReadinessProfiles token="different" contextKey="actor-b:org-b:business:active:member:read-only:industry-b" />);
    await waitFor(() => expect(screen.queryByText("Profile A")).not.toBeInTheDocument());
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
  it("discards late responses on actor/organization/entitlement context switch, including fetch failure", async () => {
    let resolveOld!: (value: Response) => void;
    const oldResponse = new Promise<Response>((resolve) => { resolveOld = resolve; });
    vi.mocked(fetch).mockReturnValueOnce(oldResponse).mockRejectedValueOnce(new Error("new context network error"));
    const { rerender } = render(<BusinessReadinessProfiles token="same-token" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    rerender(<BusinessReadinessProfiles token="same-token" contextKey="actor-b:org-b:business:active:member:read-only:industry-b" />);
    resolveOld(ok(payload()) as Response);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
    expect(screen.queryByText("Profile A")).not.toBeInTheDocument();
    expect(screen.queryByText(/stale|partial/i)).not.toBeInTheDocument();
  });
  it("shows generic error without data and never invents an empty first-use state", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("secret")); render(<BusinessReadinessProfiles token="t" contextKey="actor-a:org-a:business:active:owner:upload:industry-a" />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not load/i);
    expect(screen.queryByText(/secret|no dossiers/i)).not.toBeInTheDocument();
  });
});
