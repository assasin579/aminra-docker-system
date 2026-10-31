export const DOC_TYPE_LABEL_VI: Record<string, string> = {
  company_profile: "Hồ sơ năng lực công ty",
  halal_policy: "Chính sách Halal",
  has_manual: "Sổ tay HAS / Halal Manual",
  internal_halal_committee: "Quyết định thành lập IHC",
  ingredient_raw_material: "Danh mục nguyên vật liệu",
  process_flow_chart: "Lưu đồ quy trình sản xuất",
  sop_personal_hygiene: "SOP — Vệ sinh cá nhân",
  sop_cleaning_sanitation: "SOP — Vệ sinh cơ sở",
  sop_pest_control: "SOP — Kiểm soát côn trùng",
  sop_supplier_evaluation: "SOP — Đánh giá nhà cung cấp",
  sop_traceability: "SOP — Truy xuất nguồn gốc",
  sop_complaint_handling: "SOP — Xử lý khiếu nại",
  generic: "Tài liệu khác",
};

export function canEditDossierDocuments(
  user: { role?: string; is_owner?: boolean } | null | undefined,
  dossier: { requirements_binding_status: string; status: string } | null,
): boolean {
  return user?.role === "business" && user.is_owner === true
    && dossier?.requirements_binding_status === "bound"
    && !["cancelled", "cert_issued"].includes(dossier.status);
}
