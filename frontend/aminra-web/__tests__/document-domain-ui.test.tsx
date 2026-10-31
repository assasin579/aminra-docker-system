import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Documents from "@/app/documents/page";
import { privateCacheKey } from "@/lib/private-client-cache";
import Upload from "@/app/upload/page";
import Dossiers from "@/app/dossiers/page";
import ApprovalActions from "@/components/documents/ApprovalActions";
import type { ApprovalBlock } from "@/lib/documentVersioning";
const auth = vi.hoisted(() => ({ user: { id: "actor", tenant_id: "tenant", role: "business", is_owner: true, permissions: { can_edit: false }, industry_schema_id: "industry" }, token: "token", isAuthenticated: true, loading: false }));
const replace = vi.hoisted(() => vi.fn());
vi.mock("@/components/UserAuthContext", () => ({ useUserAuth: () => auth }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/lib/featureFlags", () => ({ useFeature: () => false, useFeatureFlags: () => ({ flags: {} }) }));
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (s: string) => s, i18n: { language: "vi" } }) }));
vi.mock("@/components/GenerateDocTab", () => ({ default: () => null, INITIAL_GENERATE_STATE: {} }));
beforeEach(() => { auth.user.role = "business"; auth.user.is_owner = true; auth.user.permissions.can_edit = false; replace.mockReset(); sessionStorage.clear(); vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ documents: [], total: 0, artifacts: [] }), { status: 200 }))); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
it("shows only an owner-selected representative and keeps older uploads in history", async () => {
  const documents = ["case-a-policy.pdf", "case-b-policy.pdf"].map((name, i) => ({
    id: `doc-${i}`, original_filename: name, doc_type: "sop_personal_hygiene", doc_type_label: null,
    compliance_score: 84, ai_score: 84, cb_score: null, overall_status: "compliant", file_size: 100,
    uploaded_at: `2026-10-${30 + i}T00:00:00Z`, uploaded_by_name: "Business", status: "uploaded", revision_count: 2, is_current_selection: i === 1,
  }));
  vi.mocked(fetch).mockImplementation(async (url) => {
    const path = String(url);
    const data = path.includes("official-artifacts") ? { artifacts: [] }
      : path.includes("/revisions/") ? { revisions: [...documents].reverse(), total: 2, doc_type: "sop_personal_hygiene" }
      : (path.includes("view=official_by_type") || path.includes("view=latest_by_type")) ? { documents: [documents[1]], total: 1 }
      : { documents, total: 2 };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  render(<Documents />);
  expect(await screen.findByText("case-b-policy.pdf")).toBeInTheDocument();
  expect(screen.queryByText("case-a-policy.pdf")).not.toBeInTheDocument();
  expect(screen.getAllByText("SOP — Vệ sinh cá nhân")).toHaveLength(1);
  expect(screen.getByRole("link", { name: "Các bộ hồ sơ" })).toHaveAttribute("href", "/dossiers");
  fireEvent.click(screen.getByTitle("Lịch sử"));
  expect(await screen.findByText("case-a-policy.pdf")).toBeInTheDocument();
  await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("/documents?view=latest_by_type&"))).toBe(true));
});
it("replaces the main card with an explicitly selected older upload without hiding history", async () => {
  const documents = ["older-policy.pdf", "newer-policy.pdf"].map((name, i) => ({
    id: `doc-${i}`, original_filename: name, doc_type: "halal_policy", doc_type_label: null,
    compliance_score: null, overall_status: null, file_size: 100,
    uploaded_at: `2026-10-${30 + i}T00:00:00Z`, uploaded_by_name: "Business", status: "uploaded", revision_count: 2,
  }));
  let selected = 1;
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.mocked(fetch).mockImplementation(async (url, options) => {
    const path = String(url);
    if (path.endsWith("/doc-0/promote") && options?.method === "POST") {
      selected = 0;
      return new Response(JSON.stringify({ changed: true }), { status: 200 });
    }
    const data = path.includes("official-artifacts") ? { artifacts: [] }
      : path.includes("/revisions/") ? {
        revisions: documents.map((doc, i) => ({ ...doc, is_current_selection: i === selected })), total: 2, doc_type: "halal_policy",
      } : { documents: (path.includes("view=official_by_type") || path.includes("view=latest_by_type")) ? [{...documents[selected],is_current_selection:true}] : documents, total: 1 };
    return new Response(JSON.stringify(data), { status: 200 });
  });
  render(<Documents />);
  expect(await screen.findByRole("heading", { name: "newer-policy.pdf" })).toBeInTheDocument();
  fireEvent.click(screen.getByTitle("Lịch sử"));
  await screen.findByText("older-policy.pdf");
  fireEvent.click(screen.getByRole("button", { name: "Chọn bản hiện hành" }));
  expect(await screen.findByRole("heading", { name: "older-policy.pdf" })).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "newer-policy.pdf" })).not.toBeInTheDocument();
  expect(screen.getByText("newer-policy.pdf")).toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.filter(([url]) => String(url).includes("view=latest_by_type")).length).toBeGreaterThanOrEqual(2);
});
it("redirects a CB out of the business dossier list before fetching it", async () => {
  auth.user.role = "provider"; render(<Dossiers />);
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/submissions"));
  expect(fetch).not.toHaveBeenCalled();
});
it.each(["saved", "failed", undefined])("restored AI report shows its actual persistence outcome: %s", async status => {
  sessionStorage.setItem(privateCacheKey("actor", "tenant", "evaluation")!, JSON.stringify({ report: {
    document_save_status: status, document_save_error: status === "failed" ? "Phân tích AI đã hoàn tất nhưng chưa lưu được vào kho tài liệu." : null,
    word_count: 100, standards_found: 2, filename: "policy.pdf", doc_type: "halal_policy", doc_type_label: "Policy", compliance_score: 80, overall_status: "compliant",
    summary: "Synthetic report", issues: [], strengths: [], recommendations: [], standards_checked: [], gap_analysis: null, risk_flags: [], citations: [],
  } }));
  render(<Upload />);
  if (status === "failed") expect(await screen.findByRole("alert")).toHaveTextContent("chưa lưu được");
  else if (status === "saved") expect(await screen.findByRole("status")).toHaveTextContent("đã lưu vào kho");
  else expect(await screen.findByRole("status")).toHaveTextContent("Chưa xác nhận");
});

it.each([
  { role: "business", owner: false },
  { role: "provider", owner: false },
  { role: "provider", owner: true },
])("only the business owner can select the library representative: $role owner=$owner", async ({ role, owner }) => {
  auth.user.role=role;auth.user.is_owner=owner;auth.user.permissions.can_edit=true;
  const docs=[0,1].map(i=>({id:`restricted-${i}`,original_filename:`restricted-${i}.pdf`,doc_type:"halal_policy",doc_type_label:null,compliance_score:null,overall_status:null,file_size:100,uploaded_at:"2026-10-31T00:00:00Z",revision_count:2,is_current_selection:i===1}));
  vi.mocked(fetch).mockImplementation(async url=>new Response(JSON.stringify(String(url).includes("official-artifacts")?{artifacts:[]}:String(url).includes("/revisions/")?{revisions:docs,total:2,doc_type:"halal_policy"}:{documents:[docs[1]],total:1}),{status:200}));
  render(<Documents />);
  fireEvent.click(await screen.findByTitle("Lịch sử"));
  await screen.findByText("restricted-0.pdf");
  expect(screen.queryByRole("button",{name:"Chọn bản hiện hành"})).not.toBeInTheDocument();
});

it("keeps dossier preparation in the same workspace for business members", async () => {
  auth.user.is_owner=false;
  vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([]),{status:200}));
  render(<Dossiers />);
  const dossiers=await screen.findByRole("link",{name:"Các bộ hồ sơ"});
  expect(dossiers).toHaveAttribute("aria-current","page");
  expect(screen.getByRole("link",{name:"Tài liệu DN"})).toHaveAttribute("href","/documents");
  expect(screen.getByTestId("dossier-create-cta")).toBeInTheDocument();
});
it("uses two workspace tabs and keeps approval snapshots as a document filter", async () => {
  render(<Documents />);
  expect(await screen.findByRole("link",{name:"Tài liệu DN"})).toHaveAttribute("aria-current","page");
  expect(screen.getByRole("link",{name:"Các bộ hồ sơ"})).toHaveAttribute("href","/dossiers");
  expect(screen.getByRole("button",{name:"Bản lưu phê duyệt"})).toBeInTheDocument();
});

it("lets an owner select the first official file from the pending type group", async () => {
  let selected: string | null=null;
  const docs=[0,1].map(i=>({id:`draft-${i}`,original_filename:`draft-${i}.pdf`,doc_type:"halal_policy",doc_type_label:"Chính sách Halal",file_size:100,compliance_score:null,overall_status:null,status:"uploaded",revision_count:2,uploaded_at:"2026-10-31T00:00:00Z"}));
  vi.spyOn(window,"confirm").mockReturnValue(true);
  vi.mocked(fetch).mockImplementation(async (url,options)=>{
    const path=String(url);if(path.endsWith("/draft-0/promote")&&options?.method==="POST"){selected="draft-0";return new Response(JSON.stringify({changed:true}),{status:200});}
    const chosen=selected?{...docs[0],is_current_selection:true}:null;
    const data=path.includes("official-artifacts")?{artifacts:[]}:path.includes("/revisions/")?{doc_type:"halal_policy",total:2,revisions:docs.map(doc=>({...doc,is_current_selection:doc.id===selected}))}:path.includes("view=official_by_type")?{documents:chosen?[chosen]:[],total:chosen?1:0}:{documents:chosen?[chosen]:[{...docs[1],is_current_selection:false}],total:1};
    return new Response(JSON.stringify(data),{status:200});
  });
  render(<Documents />);
  fireEvent.click(await screen.findByRole("button",{name:"Chọn bản chính cho Chính sách Halal"}));
  await screen.findByText("draft-0.pdf");
  const row=document.querySelector('[data-history-document-id="draft-0"]')!;
  fireEvent.click(within(row as HTMLElement).getByRole("button",{name:"Chọn bản hiện hành"}));
  expect(await screen.findByRole("heading",{name:"draft-0.pdf"})).toBeVisible();
  await waitFor(()=>expect(screen.queryByRole("region",{name:"Chờ chủ DN chọn bản chính"})).not.toBeInTheDocument());
  expect(screen.getAllByRole("button",{name:"Chọn bản hiện hành"})).toHaveLength(1);
});
it("does not expose pending selection controls to an editing member", async () => {
  auth.user.is_owner=false;auth.user.permissions.can_edit=true;
  render(<Documents />);
  await screen.findByRole("heading",{name:"Kho tài liệu"});
  expect(screen.queryByRole("region",{name:"Chờ chủ DN chọn bản chính"})).not.toBeInTheDocument();
  expect(vi.mocked(fetch).mock.calls.some(([url])=>String(url).includes("view=latest_by_type"))).toBe(false);
});
it("IHC may review approval but only an owner may designate a replacement", () => {
  const approval:ApprovalBlock={approval_status:"approved",version_number:1,version_parent_id:null,approver_id:null,approved_at:null,effective_date:null,next_review_date:null,retention_period_days:0,retention_expires_at:null,superseded_by_id:null,is_obsolete:false};
  const props={docId:"approved",approval,perms:{canEdit:true,canApproveDocuments:true,isOwner:false,isIhcMember:true},token:"fixture",onChanged:vi.fn()};
  const view=render(<ApprovalActions {...props}/>);expect(screen.queryByRole("button",{name:"Thay thế"})).not.toBeInTheDocument();
  view.rerender(<ApprovalActions {...props} approval={{...approval,approval_status:"pending_approval"}}/>);
  expect(screen.getByRole("button",{name:"Phê duyệt"})).toBeInTheDocument();
});

it("a fresh upload appears in the owner pending group without becoming official automatically", async () => {
 let uploaded=false;
 vi.mocked(fetch).mockImplementation(async (url,options)=>{
  const path=String(url);
  if(path.endsWith("/documents/upload")&&options?.method==="POST"){uploaded=true;return new Response(JSON.stringify({id:"fresh"}),{status:200});}
  const data=path.includes("official-artifacts")?{artifacts:[]}:path.includes("view=latest_by_type")&&uploaded?{documents:[{id:"fresh",original_filename:"fresh.pdf",doc_type:"halal_policy",is_current_selection:false}],total:1}:{documents:[],total:0};
  return new Response(JSON.stringify(data),{status:200});
 });
 render(<Documents />);
 fireEvent.click(screen.getAllByRole("button",{name:/Upload tài liệu/})[0]);
 const modal=screen.getByRole("dialog");fireEvent.click(within(modal).getByRole("button",{name:"Halal Policy"}));
 const input=modal.querySelector('input[type="file"]')!;
 fireEvent.change(input,{target:{files:[new File(["%PDF-1.4"],"fresh.pdf",{type:"application/pdf"})]}});
 expect(await screen.findByRole("button",{name:"Chọn bản chính cho Chính sách Halal"})).toBeVisible();
 expect(screen.queryByRole("heading",{name:"fresh.pdf"})).not.toBeInTheDocument();
 expect(vi.mocked(fetch).mock.calls.some(([url])=>String(url).endsWith("/promote"))).toBe(false);
});
