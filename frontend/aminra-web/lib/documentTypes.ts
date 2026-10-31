export const DOC_TYPE_OPTIONS = [
  { id: "halal_policy", label: "Halal Policy", group: "policy" },
  { id: "has_manual", label: "HAS Manual", group: "policy" },
  { id: "halal_manual", label: "Halal Manual", group: "policy" },
  {
    id: "internal_halal_committee",
    label: "Internal Halal Committee",
    group: "policy",
  },
  { id: "company_profile", label: "Company Profile", group: "policy" },
  {
    id: "ingredient_raw_material",
    label: "Ingredient & Raw Material Documentation",
    group: "tech",
  },
  { id: "process_flow_chart", label: "Process Flow Chart", group: "tech" },
];

export const SOP_SUB_OPTIONS = [
  { id: "sop_raw_material_receiving", label: "Raw Material Receiving" },
  { id: "sop_storage_segregation", label: "Storage and Segregation" },
  { id: "sop_production_operation", label: "Production or Service Operation" },
  { id: "sop_cleaning_sanitation", label: "Cleaning and Sanitation" },
  { id: "sop_handling_nonconformances", label: "Handling Non-Conformances" },
  { id: "sop_complaint_recall", label: "Complaint and Recall Management" },
];

export const DOC_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  [...DOC_TYPE_OPTIONS, ...SOP_SUB_OPTIONS].map((d) => [d.id, d.label]),
);

const DOC_TYPE_LABEL_VI_BASE: Record<string, string> = {
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

export const DOC_TYPE_LABEL_VI: Record<string, string> = {
  ...DOC_TYPE_LABELS, ...DOC_TYPE_LABEL_VI_BASE,
};
