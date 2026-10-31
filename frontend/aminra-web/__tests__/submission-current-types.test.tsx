import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import Page from "@/app/submissions/page";
const route = vi.hoisted(() => ({ dossier: "" }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams(route.dossier ? `dossier_id=${route.dossier}` : "") }));
vi.mock("@/components/UserAuthContext", () => ({ useUserAuth: () => ({ user: { id: "owner", tenant_id: "tenant", role: "business", is_owner: true }, token: "fixture-token", isAuthenticated: true, loading: false }) }));
const old = { id: "policy-old", doc_type: "policy", original_filename: "policy-selected.pdf", doc_type_label: "Chính sách" };
const newer = { ...old, id: "policy-new", original_filename: "policy-hidden.pdf" };
const other = { id: "procedure", doc_type: "procedure", original_filename: "procedure.pdf", doc_type_label: "Quy trình" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
let attached = [old, newer, other];
beforeEach(() => {
 route.dossier = ""; attached = [old, newer, other];
 vi.stubGlobal("fetch", vi.fn(async (input: string) => {
  const url = String(input);
  if (url.endsWith("/providers")) return json({ providers: [{ id: "cb", company_name: "CB fixture", email: "cb@example.invalid" }] });
  if (url.includes("/api/api/documents?")) return json({ documents: url.includes("view=latest_by_type") ? [old, other] : [old, newer, other], total: url.includes("view=latest_by_type") ? 2 : 3 });
  if (url.endsWith("/dossiers/dossier-A")) return json({ id: "dossier-A", title: "Dossier A", requirements_binding_status: "bound", documents: attached });
  if (url.endsWith("/submit")) return json({ id: "submission" });
  return json({ submissions: [] });
 }));
});
afterEach(() => vi.unstubAllGlobals());
for (const dossier of ["", "dossier-A"]) {
 test(`three files become two type representatives; send only their IDs (${dossier || "direct"})`, async () => {
  route.dossier = dossier; render(<Page />);
  fireEvent.click(await screen.findByRole("button", { name: /Gửi hồ sơ mới/ }));
  await screen.findByText("policy-selected.pdf");
  expect(screen.queryByText("policy-hidden.pdf")).not.toBeInTheDocument();
  expect(screen.getByText("procedure.pdf")).toBeInTheDocument();
  expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: /CB fixture cb@example.invalid/ }));
  fireEvent.click(screen.getByRole("button", { name: "Gửi 2 tài liệu" }));
  const call = vi.mocked(fetch).mock.calls.find(([url]) => String(url).endsWith("/submit"));
  expect(call).toBeDefined();
  expect(JSON.parse(String(call![1]?.body)).document_ids).toEqual(["policy-old", "procedure"]);
 });
}
test("a dossier cannot silently substitute a library representative never attached", async () => {
 route.dossier = "dossier-A"; attached = [newer, other]; render(<Page />);
 fireEvent.click(await screen.findByRole("button", { name: /Gửi hồ sơ mới/ }));
 expect(await screen.findByRole("alert")).toHaveTextContent("tài liệu đại diện");
 expect(screen.getByRole("button", { name: "Gửi 0 tài liệu" })).toBeDisabled();
});

test("representatives beyond the first 100 types remain available", async () => {
 const { loadSubmissionDocuments } = await import("@/lib/submissionDocuments");
 const first = Array.from({ length: 100 }, (_, i) => ({ id: `file-${i}`, doc_type: `type-${i}`, original_filename: `file-${i}.pdf` }));
 vi.mocked(fetch).mockReset().mockResolvedValueOnce(json({ documents: first, total: 101 })).mockResolvedValueOnce(json({ documents: [other], total: 101 }));
 expect(await loadSubmissionDocuments("fixture-token")).toHaveLength(101);
 expect(String(vi.mocked(fetch).mock.calls[1][0])).toContain("page=2");
});

test("a changing paginated selection cannot offer two representatives of the same type", async () => {
 const { loadSubmissionDocuments } = await import("@/lib/submissionDocuments");
 const first = Array.from({ length: 100 }, (_, i) => ({ id: `file-${i}`, doc_type: `type-${i}`, original_filename: `file-${i}.pdf` }));
 vi.mocked(fetch).mockReset().mockResolvedValueOnce(json({ documents: first, total: 101 })).mockResolvedValueOnce(json({ documents: [{ ...first[0], id: "replacement" }], total: 101 }));
 await expect(loadSubmissionDocuments("fixture-token")).rejects.toThrow("đã thay đổi");
});

test("a later page failure never returns an incomplete send list", async () => {
 const { loadSubmissionDocuments } = await import("@/lib/submissionDocuments");
 const first = Array.from({ length: 100 }, (_, i) => ({ id: `file-${i}`, doc_type: `type-${i}`, original_filename: `file-${i}.pdf` }));
 vi.mocked(fetch).mockReset().mockResolvedValueOnce(json({ documents: first, total: 101 })).mockResolvedValueOnce(json({}, 503));
 await expect(loadSubmissionDocuments("fixture-token")).rejects.toThrow("Không tải được");
});
