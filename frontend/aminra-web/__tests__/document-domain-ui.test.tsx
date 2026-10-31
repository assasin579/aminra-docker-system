import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Documents from "@/app/documents/page";
import Upload from "@/app/upload/page";
import Dossiers from "@/app/dossiers/page";
const auth = vi.hoisted(() => ({ user: { id: "actor", role: "business", is_owner: true, industry_schema_id: "industry" }, token: "token", isAuthenticated: true, loading: false }));
const replace = vi.hoisted(() => vi.fn());
vi.mock("@/components/UserAuthContext", () => ({ useUserAuth: () => auth }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/featureFlags", () => ({ useFeature: () => false, useFeatureFlags: () => ({ flags: {} }) }));
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (s: string) => s, i18n: { language: "vi" } }) }));
vi.mock("@/components/GenerateDocTab", () => ({ default: () => null, INITIAL_GENERATE_STATE: {} }));
beforeEach(() => { auth.user.role = "business"; replace.mockReset(); sessionStorage.clear(); vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ documents: [], total: 0, artifacts: [] }), { status: 200 }))); });
afterEach(() => vi.unstubAllGlobals());
it("requests all library files and links to dossier preparation", async () => {
  vi.mocked(fetch).mockImplementation(async (url) => new Response(JSON.stringify(String(url).includes("official-artifacts") ? { artifacts: [] } : {
    documents: ["case-a-policy.pdf", "case-b-policy.pdf"].map((name, i) => ({
      id: `doc-${i}`, original_filename: name, doc_type: "sop_personal_hygiene", doc_type_label: null,
      compliance_score: 84, ai_score: 84, cb_score: null, overall_status: "compliant", file_size: 100,
      uploaded_at: "2026-10-31T00:00:00Z", uploaded_by_name: "Business", status: "uploaded", revision_count: 2,
    })), total: 2,
  }), { status: 200 }));
  render(<Documents />);
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("/documents?view=all&"))).toBe(true));
  expect(screen.getByRole("link", { name: "Hồ sơ chứng nhận" })).toHaveAttribute("href", "/dossiers");
  expect(await screen.findByText("case-a-policy.pdf")).toBeInTheDocument();
  expect(screen.getByText("case-b-policy.pdf")).toBeInTheDocument();
  expect(screen.getAllByText("SOP — Vệ sinh cá nhân")).toHaveLength(2);
});
it("redirects a CB out of the business dossier list before fetching it", async () => {
  auth.user.role = "provider"; render(<Dossiers />);
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/submissions"));
  expect(fetch).not.toHaveBeenCalled();
});
it.each(["saved", "failed", undefined])("restored AI report shows its actual persistence outcome: %s", async status => {
  sessionStorage.setItem("aminra_eval_actor", JSON.stringify({ report: {
    document_save_status: status, document_save_error: status === "failed" ? "Phân tích AI đã hoàn tất nhưng chưa lưu được vào kho tài liệu." : null,
    word_count: 100, standards_found: 2, filename: "policy.pdf", doc_type: "halal_policy", doc_type_label: "Policy", compliance_score: 80, overall_status: "compliant",
    summary: "Synthetic report", issues: [], strengths: [], recommendations: [], standards_checked: [], gap_analysis: null, risk_flags: [], citations: [],
  } }));
  render(<Upload />);
  if (status === "failed") expect(await screen.findByRole("alert")).toHaveTextContent("chưa lưu được");
  else if (status === "saved") expect(await screen.findByRole("status")).toHaveTextContent("đã lưu vào kho");
  else expect(await screen.findByRole("status")).toHaveTextContent("Chưa xác nhận");
});
