"use client";

import { useState, useEffect } from "react";
import { useUserAuth } from "@/components/UserAuthContext";
import Link from "next/link";

interface StandardSummary {
  id: string;
  code: string;
  name_vi: string;
  is_default: boolean;
}

interface IndustrySchemaSummary {
  id: string;
  code: string;
  name_vi: string;
  name_en: string | null;
  description: string | null;
  icon: string | null;
  available_standards: StandardSummary[];
}

interface CompanyForm {
  // Tab 1 — Identity
  company_name: string;
  representative_name: string;
  address: string;
  phone: string;
  email: string;
  manager_name: string;
  // Tab 2 — Halal compliance
  founded_year: string;
  total_employees: string;
  halal_commitment_statement: string;
  najis_handling_policy: string;
  cross_contamination_controls: string;
  // Tab 3 — Products & ingredients
  product_categories: string;
  primary_suppliers: string;
  ingredient_origin_countries: string;
  packaging_materials_brief: string;
  // Tab 4 — IHC
  ihc_chairman_name: string;
  ihc_chairman_title: string;
  ihc_inception_date: string;
  ihc_members_brief: string;
  ihc_meeting_frequency: string;
  // Tab 5 — Production
  production_capacity_brief: string;
}

const EMPTY_FORM: CompanyForm = {
  company_name: "",
  representative_name: "",
  address: "",
  phone: "",
  email: "",
  manager_name: "",
  founded_year: "",
  total_employees: "",
  halal_commitment_statement: "",
  najis_handling_policy: "",
  cross_contamination_controls: "",
  product_categories: "",
  primary_suppliers: "",
  ingredient_origin_countries: "",
  packaging_materials_brief: "",
  ihc_chairman_name: "",
  ihc_chairman_title: "",
  ihc_inception_date: "",
  ihc_members_brief: "",
  ihc_meeting_frequency: "",
  production_capacity_brief: "",
};

const INDUSTRY_ICON_MAP: Record<string, string> = {
  factory: "🏭",
  restaurant: "🏨",
  cow: "🐄",
  pharmacy: "💊",
  cosmetic: "💄",
  truck: "🚛",
};

type FieldKey = keyof CompanyForm;
type FieldDef = {
  key: FieldKey;
  label: string;
  placeholder: string;
  type?: "text" | "tel" | "email" | "number" | "date" | "textarea";
};

const TABS = [
  { id: "identity", label: "Cơ bản", icon: "🏷️" },
  { id: "halal", label: "Tuân thủ Halal", icon: "🌙" },
  { id: "products", label: "Sản phẩm & Nguyên liệu", icon: "📦" },
  { id: "ihc", label: "IHC", icon: "👥" },
  { id: "production", label: "Sản xuất", icon: "🏭" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const FIELDS_BY_TAB: Record<TabId, FieldDef[]> = {
  identity: [
    { key: "company_name", label: "Tên công ty", placeholder: "VD: Công ty TNHH Thực phẩm ABC" },
    { key: "representative_name", label: "Giám đốc / Người đại diện", placeholder: "VD: Nguyễn Văn A" },
    { key: "address", label: "Địa chỉ", placeholder: "VD: 123 Nguyễn Huệ, Q.1, TP.HCM" },
    { key: "phone", label: "Số điện thoại", placeholder: "VD: 028-1234-5678", type: "tel" },
    { key: "email", label: "Email công ty", placeholder: "VD: info@abc.com.vn", type: "email" },
    { key: "manager_name", label: "Người quản lý hệ thống (Admin DN)", placeholder: "VD: Trần Văn B" },
  ],
  halal: [
    { key: "founded_year", label: "Năm thành lập", placeholder: "VD: 2015", type: "number" },
    { key: "total_employees", label: "Tổng số nhân viên", placeholder: "VD: 120", type: "number" },
    {
      key: "halal_commitment_statement",
      label: "Tuyên bố cam kết Halal",
      placeholder: "VD: Công ty cam kết tuân thủ nghiêm ngặt các nguyên tắc Halal trong toàn bộ chuỗi sản xuất...",
      type: "textarea",
    },
    {
      key: "najis_handling_policy",
      label: "Chính sách xử lý Najis",
      placeholder: "VD: Tất cả thiết bị tiếp xúc với najis đều được rửa 7 lần (1 lần với đất sét)...",
      type: "textarea",
    },
    {
      key: "cross_contamination_controls",
      label: "Kiểm soát nhiễm chéo",
      placeholder: "VD: Khu vực Halal/Haram tách biệt vật lý; dụng cụ riêng; quy trình vệ sinh đệm thời gian...",
      type: "textarea",
    },
  ],
  products: [
    {
      key: "product_categories",
      label: "Danh mục sản phẩm chính",
      placeholder: "VD: Thịt bò, gia cầm chế biến, đồ uống không cồn (CSV)",
      type: "textarea",
    },
    {
      key: "primary_suppliers",
      label: "Nhà cung cấp chính",
      placeholder: "VD: Công ty TNHH Nguyên liệu ABC, Halal Meat Co. (CSV)",
      type: "textarea",
    },
    {
      key: "ingredient_origin_countries",
      label: "Quốc gia xuất xứ nguyên liệu",
      placeholder: "VD: VN, MY, AU, BR (mã ISO, CSV)",
    },
    {
      key: "packaging_materials_brief",
      label: "Vật liệu đóng gói",
      placeholder: "VD: PET bottle, paperboard, HDPE film...",
      type: "textarea",
    },
  ],
  ihc: [
    { key: "ihc_chairman_name", label: "Chủ tịch IHC", placeholder: "VD: Ahmad Bin Abdullah" },
    { key: "ihc_chairman_title", label: "Chức danh Chủ tịch IHC", placeholder: "VD: Halal Compliance Director" },
    { key: "ihc_inception_date", label: "Ngày thành lập IHC", placeholder: "", type: "date" },
    {
      key: "ihc_members_brief",
      label: "Thành viên IHC (tóm tắt)",
      placeholder: "VD: 5 thành viên gồm: Giám đốc sản xuất, QA Manager, Halal Auditor nội bộ...",
      type: "textarea",
    },
    {
      key: "ihc_meeting_frequency",
      label: "Tần suất họp IHC",
      placeholder: "VD: Hàng tháng / Hàng quý",
    },
  ],
  production: [
    {
      key: "production_capacity_brief",
      label: "Năng lực sản xuất (tóm tắt)",
      placeholder: "VD: 500 tấn/tháng. 3 dây chuyền chế biến thịt, 1 dây chuyền đóng gói. Khu vực Halal: 1500 m²...",
      type: "textarea",
    },
  ],
};

export default function CompanySettingsPage() {
  const { user, token, isAuthenticated } = useUserAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [industry, setIndustry] = useState<IndustrySchemaSummary | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("identity");
  const [form, setForm] = useState<CompanyForm>(EMPTY_FORM);

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    setLoading(true);
    Promise.all([
      fetch("/api/auth/company-profile", { headers }).then((r) =>
        r.ok ? r.json() : null,
      ),
      user?.industry_schema_code
        ? fetch(`/api/industry-schemas/${user.industry_schema_code}`, {
            headers,
          }).then((r) => (r.ok ? r.json() : null))
        : Promise.resolve(null),
    ])
      .then(([data, industryData]) => {
        if (data) {
          // Coerce nulls/numerics to string for form state
          const next: CompanyForm = { ...EMPTY_FORM };
          for (const k of Object.keys(EMPTY_FORM) as FieldKey[]) {
            const v = (data as Record<string, unknown>)[k];
            next[k] = v == null ? "" : String(v);
          }
          setForm(next);
        }
        if (industryData) setIndustry(industryData);
      })
      .catch(() => setError("Không thể tải thông tin"))
      .finally(() => setLoading(false));
  }, [isAuthenticated, token, user?.industry_schema_code]);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      // Build payload — null for empty strings, coerce numerics
      const payload: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(form)) {
        if (v === "" || v === null) {
          payload[k] = null;
        } else if (k === "founded_year" || k === "total_employees") {
          const n = Number(v);
          payload[k] = Number.isFinite(n) ? n : null;
        } else {
          payload[k] = v;
        }
      }

      const res = await fetch("/api/auth/company-profile", {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.detail || "Lưu thất bại");
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Không thể lưu");
    } finally {
      setSaving(false);
    }
  };

  const updateField = (key: FieldKey, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  // Calculate tab completion %
  const tabCompletionPct = (tabId: TabId): number => {
    const fs = FIELDS_BY_TAB[tabId];
    if (fs.length === 0) return 100;
    const filled = fs.filter((f) => form[f.key].trim() !== "").length;
    return Math.round((filled / fs.length) * 100);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="text-center space-y-4">
          <p style={{ color: "#6B7280" }}>Vui lòng đăng nhập</p>
          <Link
            href="/business/login"
            className="inline-block px-6 py-3 rounded-xl font-semibold text-white btn-lift"
            style={{ background: "#0A1F44" }}
          >
            Đăng nhập
          </Link>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" style={{ animationDelay: "0.15s" }} />
          <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" style={{ animationDelay: "0.3s" }} />
        </div>
      </div>
    );
  }

  const isOwner = user?.is_owner;
  const cardStyle = { background: "#FFFFFF", border: "1px solid #E2E8F0" };
  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };

  const activeFields = FIELDS_BY_TAB[activeTab];

  return (
    <div style={{ background: "#FFFFFF" }} data-page>
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
            Thông tin doanh nghiệp
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            Thông tin được tự động dùng để fill placeholder khi tạo tài liệu Halal.
            Fill càng đầy đủ, % real data càng cao, càng ít placeholder content trong tài liệu xuất ra.
          </p>
        </div>

        {/* Industry block — always visible */}
        <div className="rounded-2xl p-5" style={cardStyle}>
          <label className="block text-xs font-medium mb-2" style={{ color: "#6B7280" }}>
            Ngành nghề doanh nghiệp
          </label>
          {industry ? (
            <div
              className="rounded-xl p-4"
              style={{
                background: "rgba(10,31,68,0.04)",
                border: "1px solid #E2E8F0",
              }}
              data-testid="industry-display-block"
            >
              <div className="flex items-start gap-3">
                <div className="text-3xl leading-none">
                  {INDUSTRY_ICON_MAP[industry.icon ?? ""] ?? "📋"}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
                    {industry.name_vi}
                  </div>
                  {industry.description && (
                    <div className="text-xs mt-2" style={{ color: "#6B7280" }}>
                      {industry.description}
                    </div>
                  )}
                  {industry.available_standards.length > 0 && (
                    <div className="text-[11px] mt-3" style={{ color: "#6B7280" }}>
                      Tiêu chuẩn áp dụng được:{" "}
                      {industry.available_standards
                        .map((s) => s.name_vi.split(" — ")[0] + (s.is_default ? " ★" : ""))
                        .join(" · ")}
                    </div>
                  )}
                  <div className="text-[11px] mt-3" style={{ color: "#94A3B8" }}>
                    🔒 Khóa sau khi cert đầu tiên đã issue. Liên hệ AMINRA admin nếu cần đổi.
                  </div>
                </div>
              </div>
            </div>
          ) : isOwner ? (
            <div
              className="rounded-xl p-4 text-xs"
              style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}
            >
              Chưa chọn ngành nghề.{" "}
              <Link href="/business/onboarding/industry-select" className="underline font-medium">
                Chọn ngay
              </Link>
            </div>
          ) : (
            <div className="rounded-xl p-4 text-xs" style={{ background: "#F3F4F6", color: "#6B7280" }}>
              Chưa được chủ tài khoản chọn ngành nghề
            </div>
          )}
        </div>

        {!isOwner && (
          <div
            className="px-4 py-3 rounded-lg text-xs leading-relaxed"
            style={{ background: "#FFFBEB", border: "1px solid #FDE68A", color: "#B45309" }}
          >
            <strong>Tài khoản thành viên.</strong> Thông tin công ty được quản lý
            bởi chủ tài khoản đã mời bạn.
          </div>
        )}

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {TABS.map((t) => {
            const active = activeTab === t.id;
            const pct = tabCompletionPct(t.id);
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className="px-4 py-2 rounded-lg text-sm font-medium btn-lift"
                style={{
                  background: active ? "#0A1F44" : "#F1F5F9",
                  color: active ? "white" : "#0A1F44",
                  border: active ? "1px solid #0A1F44" : "1px solid transparent",
                }}
                data-testid={`tab-${t.id}`}
              >
                <span className="mr-1">{t.icon}</span>
                {t.label}
                <span
                  className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full font-mono"
                  style={{
                    background: active ? "rgba(255,255,255,0.2)" : "rgba(10,31,68,0.1)",
                    color: active ? "white" : "#6B7280",
                  }}
                >
                  {pct}%
                </span>
              </button>
            );
          })}
        </div>

        {/* Active tab fields */}
        <div className="rounded-2xl p-6 space-y-5" style={cardStyle}>
          <h2 className="text-base font-bold" style={{ color: "#0A1F44" }}>
            {TABS.find((t) => t.id === activeTab)?.icon}{" "}
            {TABS.find((t) => t.id === activeTab)?.label}
          </h2>

          {activeFields.map((f) => (
            <div key={f.key}>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6B7280" }}
              >
                {f.label}
              </label>
              {f.type === "textarea" ? (
                <textarea
                  value={form[f.key]}
                  onChange={(e) => updateField(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  readOnly={!isOwner}
                  rows={3}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-y"
                  style={{
                    ...inputStyle,
                    cursor: !isOwner ? "not-allowed" : "text",
                    minHeight: "80px",
                  }}
                  data-testid={`field-${f.key}`}
                />
              ) : (
                <input
                  type={f.type || "text"}
                  value={form[f.key]}
                  onChange={(e) => updateField(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  readOnly={!isOwner}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={{
                    ...inputStyle,
                    cursor: !isOwner ? "not-allowed" : "text",
                  }}
                  data-testid={`field-${f.key}`}
                />
              )}
            </div>
          ))}
        </div>

        {error && (
          <div
            className="px-3 py-2 rounded-lg text-xs"
            style={{ background: "#FEF2F2", border: "1px solid #FECACA", color: "#DC2626" }}
          >
            {error}
          </div>
        )}
        {saved && (
          <div
            className="px-3 py-2 rounded-lg text-xs"
            style={{ background: "#DCE3F0", border: "1px solid #D9B96E", color: "#102A5C" }}
          >
            Đã lưu thành công
          </div>
        )}

        {isOwner && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full px-4 py-2.5 rounded-lg text-sm font-medium btn-lift"
            style={{
              background: saving ? "#94A3B8" : "#0A1F44",
              color: "white",
              cursor: saving ? "not-allowed" : "pointer",
            }}
            data-testid="company-save-btn"
          >
            {saving ? "Đang lưu..." : "Lưu thông tin (toàn bộ tab)"}
          </button>
        )}

        <div className="pb-6" />
      </div>
    </div>
  );
}
