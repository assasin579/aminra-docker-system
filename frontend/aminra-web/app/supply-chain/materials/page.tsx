"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import { openAuthed } from "@/lib/authedOpen";
import Modal from "@/components/Modal";
import { ApiClientError, apiFetch } from "@/lib/apiClient";

// ── Types ────────────────────────────────────────────────────────────────────

interface Supplier {
  id: string;
  name: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  contact_person: string | null;
  supplier_type: string | null;
  status: string;
  notes: string | null;
  material_count: number;
  cert_count: number;
  created_at: string;
}

interface Certificate {
  id: string;
  cert_type: string | null;
  cert_number: string | null;
  issuing_body: string | null;
  issued_date: string | null;
  expiry_date: string | null;
  original_filename: string | null;
  file_size: number | null;
  created_at: string;
}

interface Material {
  id: string;
  name: string;
  sku: string | null;
  category: string | null;
  halal_risk: string;
  description: string | null;
  unit: string | null;
  supplier_id: string;
  supplier_name: string | null;
  created_at: string;
}

interface CertificateRiskAlert {
  id: string;
  supplier_id: string;
  supplier_name: string | null;
  event_type: string;
  severity: string;
  message: string;
  status: string;
  created_at: string;
}

const CATEGORIES = [
  { id: "meat", label: "Thịt" },
  { id: "dairy", label: "Sữa" },
  { id: "grain", label: "Ngũ cốc" },
  { id: "spice", label: "Gia vị" },
  { id: "additive", label: "Phụ gia" },
  { id: "chemical", label: "Hóa chất" },
  { id: "packaging", label: "Bao bì" },
  { id: "other", label: "Khác" },
];

const RISK_COLORS: Record<
  string,
  { bg: string; color: string; label: string }
> = {
  safe: { bg: "#DCE3F0", color: "#102A5C", label: "An toàn" },
  requires_cert: { bg: "#FFFBEB", color: "#B45309", label: "Cần chứng nhận" },
  prohibited: { bg: "#FEF2F2", color: "#DC2626", label: "Cấm sử dụng" },
  unknown: { bg: "#F3F4F6", color: "#6B7280", label: "Chưa xác định" },
};

const STATUS_COLORS: Record<
  string,
  { bg: string; color: string; label: string }
> = {
  pending: { bg: "#F3F4F6", color: "#6B7280", label: "Chờ xác minh" },
  verified: { bg: "#DCE3F0", color: "#102A5C", label: "Đã xác minh" },
  expired: { bg: "#FEF2F2", color: "#DC2626", label: "Hết hạn" },
  suspended: { bg: "#FFFBEB", color: "#B45309", label: "Tạm ngưng" },
};

// ── Main ─────────────────────────────────────────────────────────────────────

export default function MaterialsPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading: authLoading } = useUserAuth();

  const [activeTab, setActiveTab] = useState<"materials" | "suppliers">(
    "materials",
  );

  // Materials state
  const [materials, setMaterials] = useState<Material[]>([]);
  const [matLoading, setMatLoading] = useState(false);
  const [matSearch, setMatSearch] = useState("");
  const [matCategory, setMatCategory] = useState("");
  const [showMatForm, setShowMatForm] = useState(false);
  const [editMat, setEditMat] = useState<Material | null>(null);
  const [matForm, setMatForm] = useState({
    name: "",
    sku: "",
    category: "",
    halal_risk: "unknown",
    description: "",
    unit: "",
    supplier_id: "",
  });
  const [matSaving, setMatSaving] = useState(false);

  // Suppliers state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [eligibleSuppliers, setEligibleSuppliers] = useState<Supplier[]>([]);
  const [supLoading, setSupLoading] = useState(false);
  const [showSupForm, setShowSupForm] = useState(false);
  const [editSup, setEditSup] = useState<Supplier | null>(null);
  const [supForm, setSupForm] = useState({
    name: "",
    address: "",
    phone: "",
    email: "",
    contact_person: "",
    supplier_type: "",
    tax_code: "",
    notes: "",
  });
  const [supSaving, setSupSaving] = useState(false);

  // Certificates
  const [certsOpen, setCertsOpen] = useState<string | null>(null);
  const [certs, setCerts] = useState<Certificate[]>([]);
  const [certsLoading, setCertsLoading] = useState(false);
  const [certUploading, setCertUploading] = useState(false);
  const [certType, setCertType] = useState("halal_cert");
  const certRef = useRef<HTMLInputElement>(null);
  const [inviteLoading, setInviteLoading] = useState<string | null>(null);
  const [riskAlerts, setRiskAlerts] = useState<CertificateRiskAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertUpdating, setAlertUpdating] = useState<string | null>(null);

  const CERT_TYPES = [
    { id: "halal_cert", label: "Chứng nhận Halal" },
    { id: "business_license", label: "Giấy phép kinh doanh" },
    { id: "food_safety", label: "Chứng nhận ATTP" },
    { id: "lab_result", label: "Kết quả kiểm nghiệm" },
    { id: "iso_haccp", label: "ISO 22000 / HACCP" },
    { id: "contract", label: "Hợp đồng cung cấp" },
    { id: "other", label: "Khác" },
  ];

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || user?.role !== "business"))
      router.replace("/business/login");
  }, [authLoading, isAuthenticated, user, router]);

  // ── Fetch ──────────────────────────────────────────────────────────────────

  const fetchMaterials = useCallback(async () => {
    if (!token) return;
    setMatLoading(true);
    try {
      const params = new URLSearchParams();
      if (matSearch) params.set("search", matSearch);
      if (matCategory) params.set("category", matCategory);
      const res = await fetch(`/api/api/supply-chain/materials?${params}`, {
        headers,
      });
      if (res.ok) {
        const d = await res.json();
        setMaterials(d.materials || []);
      }
    } finally {
      setMatLoading(false);
    }
  }, [token, matSearch, matCategory]);

  const fetchSuppliers = useCallback(async () => {
    if (!token) return;
    setSupLoading(true);
    try {
      const [allRes, eligibleRes] = await Promise.all([
        fetch("/api/api/supply-chain/suppliers", { headers }),
        fetch("/api/api/supply-chain/suppliers/eligible", { headers }),
      ]);
      if (allRes.ok) {
        const d = await allRes.json();
        setSuppliers(d.suppliers || []);
      }
      if (eligibleRes.ok) {
        const d = await eligibleRes.json();
        setEligibleSuppliers(d.suppliers || []);
      }
    } finally {
      setSupLoading(false);
    }
  }, [token]);

  const fetchEligibleSuppliers = useCallback(
    async (category?: string) => {
      if (!token) return;
      const params = new URLSearchParams();
      if (category) params.set("material_category", category);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const res = await fetch(`/api/api/supply-chain/suppliers/eligible${suffix}`, {
        headers,
      });
      if (res.ok) {
        const d = await res.json();
        setEligibleSuppliers(d.suppliers || []);
      }
    },
    [token],
  );

  const fetchRiskAlerts = useCallback(async () => {
    if (!token) return;
    setAlertsLoading(true);
    try {
      const res = await fetch("/api/api/supply-chain/certificate-risk-alerts?status=open", { headers });
      if (res.ok) {
        const d = await res.json();
        setRiskAlerts(d.alerts || []);
      }
    } finally {
      setAlertsLoading(false);
    }
  }, [token]);

  const updateRiskAlert = async (id: string, status: "acknowledged" | "resolved") => {
    setAlertUpdating(id);
    try {
      await apiFetch(`/api/api/supply-chain/certificate-risk-alerts/${id}`, {
        method: "PUT",
        token,
        json: { status },
        fallbackError: "Không thể cập nhật cảnh báo",
      });
      await fetchRiskAlerts();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Không thể cập nhật cảnh báo");
    } finally {
      setAlertUpdating(null);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchSuppliers();
      fetchMaterials();
      fetchRiskAlerts();
    }
  }, [isAuthenticated, fetchSuppliers, fetchMaterials, fetchRiskAlerts]);

  useEffect(() => {
    if (isAuthenticated && showMatForm) fetchEligibleSuppliers(matForm.category);
  }, [isAuthenticated, showMatForm, matForm.category, fetchEligibleSuppliers]);

  // ── Material CRUD ──────────────────────────────────────────────────────────

  const openMatCreate = () => {
    setEditMat(null);
    setMatForm({
      name: "",
      sku: "",
      category: "",
      halal_risk: "unknown",
      description: "",
      unit: "",
      supplier_id: "",
    });
    setShowMatForm(true);
  };
  const openMatEdit = (m: Material) => {
    setEditMat(m);
    setMatForm({
      name: m.name,
      sku: m.sku || "",
      category: m.category || "",
      halal_risk: m.halal_risk,
      description: m.description || "",
      unit: m.unit || "",
      supplier_id: m.supplier_id,
    });
    setShowMatForm(true);
  };
  const saveMaterial = async () => {
    if (!matForm.name || !matForm.supplier_id) return;
    setMatSaving(true);
    try {
      // Strip empty optional strings → null so Pydantic Optional[…] validators
      // don't fail on blank inputs the user simply skipped.
      const payload: Record<string, unknown> = { ...matForm };
      for (const k of Object.keys(payload)) {
        if (payload[k] === "") payload[k] = null;
      }
      const url = editMat
        ? `/api/api/supply-chain/materials/${editMat.id}`
        : "/api/api/supply-chain/materials";
      await apiFetch(url, {
        method: editMat ? "PUT" : "POST",
        token,
        json: payload,
        fallbackError: editMat ? "Cập nhật nguyên liệu thất bại" : "Tạo nguyên liệu thất bại",
      });
      setShowMatForm(false);
      fetchMaterials();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Lưu nguyên liệu thất bại");
    } finally {
      setMatSaving(false);
    }
  };
  const deleteMaterial = async (id: string) => {
    if (!confirm("Xác nhận xoá nguyên liệu này?")) return;
    try {
      await apiFetch(`/api/api/supply-chain/materials/${id}`, {
        method: "DELETE",
        token,
        fallbackError: "Xoá nguyên liệu thất bại",
      });
      fetchMaterials();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Xoá nguyên liệu thất bại");
    }
  };

  // ── Supplier CRUD ──────────────────────────────────────────────────────────

  const openSupCreate = () => {
    setEditSup(null);
    setSupForm({
      name: "",
      address: "",
      phone: "",
      email: "",
      contact_person: "",
      supplier_type: "",
      tax_code: "",
      notes: "",
    });
    setShowSupForm(true);
  };
  const openSupEdit = (s: Supplier) => {
    setEditSup(s);
    setSupForm({
      name: s.name,
      address: s.address || "",
      phone: s.phone || "",
      email: s.email || "",
      contact_person: s.contact_person || "",
      supplier_type: s.supplier_type || "",
      tax_code: (s as any).tax_code || "",
      notes: s.notes || "",
    });
    setShowSupForm(true);
  };
  // saveSupplier is now inline in the form button
  const deleteSupplier = async (id: string) => {
    if (
      !confirm(
        "Xác nhận xoá nhà cung cấp? Nguyên liệu liên kết sẽ bị ảnh hưởng.",
      )
    )
      return;
    try {
      await apiFetch(`/api/api/supply-chain/suppliers/${id}`, {
        method: "DELETE",
        token,
        fallbackError: "Xoá nhà cung cấp thất bại",
      });
      fetchSuppliers();
      fetchMaterials();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Xoá nhà cung cấp thất bại");
    }
  };

  // ── Certificates ───────────────────────────────────────────────────────────

  const openCerts = async (supId: string) => {
    setCertsOpen(supId);
    setCertsLoading(true);
    try {
      const res = await fetch(
        `/api/api/supply-chain/suppliers/${supId}/certificates`,
        { headers },
      );
      if (res.ok) {
        const d = await res.json();
        setCerts(d.certificates || []);
      }
    } finally {
      setCertsLoading(false);
    }
  };
  const uploadCert = async (supId: string, file: File) => {
    setCertUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("cert_type", certType);
      await apiFetch(
        `/api/api/supply-chain/suppliers/${supId}/certificates`,
        { method: "POST", token, body: fd, fallbackError: "Upload thất bại" },
      );
      openCerts(supId);
      fetchSuppliers();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Upload thất bại");
    } finally {
      setCertUploading(false);
      if (certRef.current) certRef.current.value = "";
    }
  };
  const viewCert = (supId: string, certId: string) => {
    openAuthed(
      `/api/api/supply-chain/suppliers/${supId}/certificates/${certId}/view`,
      token || "",
    );
  };
  const deleteCert = async (supId: string, certId: string) => {
    if (!confirm("Xoá chứng chỉ này?")) return;
    try {
      await apiFetch(
        `/api/api/supply-chain/suppliers/${supId}/certificates/${certId}`,
        { method: "DELETE", token, fallbackError: "Xoá chứng chỉ thất bại" },
      );
      openCerts(supId);
      fetchSuppliers();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Xoá chứng chỉ thất bại");
    }
  };

  // ── Invite & Verify ─────────────────────────────────────────────────────────

  const sendInvite = async (supId: string) => {
    setInviteLoading(supId);
    try {
      const data = await apiFetch(
        `/api/api/supply-chain/suppliers/${supId}/invite`,
        { method: "POST", token, fallbackError: "Lỗi tạo link" },
      ).then((res) => res.json());
      const fullUrl = `${window.location.origin}${data.portal_url}`;
      await navigator.clipboard.writeText(fullUrl);
      alert(
        `Đã copy link mời:\n${fullUrl}\n\nGửi link này cho nhà cung cấp để họ upload hồ sơ.`,
      );
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Lỗi tạo link");
    } finally {
      setInviteLoading(null);
    }
  };

  const verifySupplier = async (supId: string) => {
    try {
      await apiFetch(`/api/api/supply-chain/suppliers/${supId}/verify`, {
        method: "POST",
        token,
        fallbackError: "Không thể xác minh",
      });
      alert("Đã xác minh nhà cung cấp!");
      fetchSuppliers();
    } catch (err) {
      alert(err instanceof ApiClientError ? err.message : "Không thể xác minh");
    }
  };

  // ── Guards ─────────────────────────────────────────────────────────────────

  if (authLoading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-[#0A1F44] border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };
  const cardStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      data-page
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden"
    >
      {/* Header */}
      <div
        className="rounded-2xl p-6 mb-5 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl grid place-items-center"
              style={{
                background: "rgba(10,31,68,0.12)",
                border: "1px solid rgba(10,31,68,0.25)",
              }}
            >
              <svg
                className="w-5 h-5"
                style={{ color: "#0A1F44" }}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="1.8"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
                Nguyên vật liệu đầu vào
              </h1>
              <p className="text-sm" style={{ color: "#6B7280" }}>
                {materials.length} nguyên liệu · {suppliers.length} nhà cung cấp
              </p>
            </div>
          </div>
          <button
            onClick={activeTab === "materials" ? openMatCreate : openSupCreate}
            className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
            style={{ background: "#0A1F44" }}
          >
            +{" "}
            {activeTab === "materials"
              ? "Thêm nguyên liệu"
              : "Thêm nhà cung cấp"}
          </button>
        </div>
      </div>


      {(riskAlerts.length > 0 || alertsLoading) && (
        <div
          className="rounded-2xl p-4 mb-5 animate-section"
          style={{ background: "#FEF2F2", border: "1px solid #FECACA" }}
          role="region"
          aria-label="Cảnh báo chứng nhận NCC"
        >
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <h2 className="text-sm font-bold" style={{ color: "#991B1B" }}>
                Cảnh báo chứng nhận NCC
              </h2>
              <p className="text-xs mt-1" style={{ color: "#7F1D1D" }}>
                NCC bị hết hạn/thu hồi/tạm ngưng có thể ảnh hưởng đến nguyên liệu và lô hàng mới.
              </p>
            </div>
            <span
              className="px-2 py-1 rounded-lg text-xs font-semibold"
              style={{ background: "#FFFFFF", color: "#991B1B", border: "1px solid #FECACA" }}
            >
              {alertsLoading ? "Đang tải..." : `${riskAlerts.length} cảnh báo mở`}
            </span>
          </div>
          <div className="mt-3 space-y-2">
            {riskAlerts.slice(0, 3).map((riskAlert) => (
              <div
                key={riskAlert.id}
                className="flex items-center justify-between gap-3 rounded-xl p-3 flex-wrap"
                style={{ background: "#FFFFFF", border: "1px solid #FECACA" }}
              >
                <div className="min-w-[220px] flex-1">
                  <div className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
                    {riskAlert.supplier_name || "NCC"} · {riskAlert.severity.toUpperCase()}
                  </div>
                  <div className="text-xs mt-1" style={{ color: "#6B7280" }}>
                    {riskAlert.message}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => updateRiskAlert(riskAlert.id, "acknowledged")}
                    disabled={alertUpdating === riskAlert.id}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-60"
                    style={{ background: "#FFFBEB", color: "#92400E", border: "1px solid #FDE68A" }}
                  >
                    Đã xem
                  </button>
                  <button
                    type="button"
                    onClick={() => updateRiskAlert(riskAlert.id, "resolved")}
                    disabled={alertUpdating === riskAlert.id}
                    className="px-3 py-1.5 rounded-lg text-xs font-semibold disabled:opacity-60"
                    style={{ background: "#DCE3F0", color: "#102A5C", border: "1px solid #C7D2FE" }}
                  >
                    Đã xử lý
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sub-tabs */}
      <div
        className="grid grid-cols-2 gap-1 mb-5 p-1 rounded-xl animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        {[
          {
            id: "materials" as const,
            label: "Nguyên phụ liệu",
            count: materials.length,
          },
          {
            id: "suppliers" as const,
            label: "Nhà cung cấp",
            count: suppliers.length,
          },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={{
              background: activeTab === tab.id ? "#0A1F44" : "transparent",
              color: activeTab === tab.id ? "#FFFFFF" : "#6B7280",
              boxShadow:
                activeTab === tab.id ? "0 2px 8px rgba(10,31,68,0.25)" : "none",
            }}
          >
            {tab.label}
            <span
              className="px-1.5 py-0.5 rounded text-xs"
              style={{
                background:
                  activeTab === tab.id ? "rgba(255,255,255,0.2)" : "#E2E8F0",
              }}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* ── Tab: Materials ── */}
      {activeTab === "materials" && (
        <div
          key="materials"
          className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3 animate-tab-content"
        >
          {/* Search + filter */}
          <div className="flex gap-2 flex-wrap mb-3">
            <input
              type="text"
              placeholder="Tìm theo tên hoặc SKU..."
              value={matSearch}
              onChange={(e) => setMatSearch(e.target.value)}
              className="flex-1 min-w-[200px] px-4 py-2.5 rounded-xl text-sm outline-none"
              style={inputStyle}
            />
            <select
              value={matCategory}
              onChange={(e) => setMatCategory(e.target.value)}
              className="px-4 py-2.5 rounded-xl text-sm outline-none"
              style={inputStyle}
            >
              <option value="">Tất cả phân loại</option>
              {CATEGORIES.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </div>

          {matLoading ? (
            <div className="py-12 flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.15s" }}
              />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.3s" }}
              />
            </div>
          ) : materials.length === 0 ? (
            <div
              className="rounded-2xl p-12 text-center animate-scale-in"
              style={cardStyle}
            >
              <p className="font-semibold" style={{ color: "#0A1F44" }}>
                Chưa có nguyên liệu nào
              </p>
              <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
                Thêm nhà cung cấp trước, sau đó tạo nguyên liệu liên kết
              </p>
            </div>
          ) : (
            materials.map((m, idx) => {
              const risk = RISK_COLORS[m.halal_risk] || RISK_COLORS.unknown;
              const cat = CATEGORIES.find((c) => c.id === m.category);
              return (
                <div
                  key={m.id}
                  className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                  style={cardStyle}
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span
                          className="text-sm font-semibold"
                          style={{ color: "#0A1F44" }}
                        >
                          {m.name}
                        </span>
                        {m.sku && (
                          <span
                            className="text-xs px-2 py-0.5 rounded"
                            style={{ background: "#F0F9FF", color: "#0369A1" }}
                          >
                            {m.sku}
                          </span>
                        )}
                        <span
                          className="text-xs px-2 py-0.5 rounded animate-chip"
                          style={{ background: risk.bg, color: risk.color }}
                        >
                          {risk.label}
                        </span>
                        {cat && (
                          <span
                            className="text-xs"
                            style={{ color: "#9CA3AF" }}
                          >
                            {cat.label}
                          </span>
                        )}
                      </div>
                      <p className="text-xs" style={{ color: "#6B7280" }}>
                        NCC: {m.supplier_name || "—"} {m.unit && `· ${m.unit}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openMatEdit(m)}
                        title="Sửa"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#F0F9FF",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#0369A1" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => deleteMaterial(m.id)}
                        title="Xoá"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#FEF2F2",
                          border: "1px solid #FECACA",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#DC2626" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Tab: Suppliers ── */}
      {activeTab === "suppliers" && (
        <div
          key="suppliers"
          className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3 animate-tab-content"
        >
          {supLoading ? (
            <div className="py-12 flex items-center justify-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.15s" }}
              />
              <div
                className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                style={{ animationDelay: "0.3s" }}
              />
            </div>
          ) : suppliers.length === 0 ? (
            <div
              className="rounded-2xl p-12 text-center animate-scale-in"
              style={cardStyle}
            >
              <p className="font-semibold" style={{ color: "#0A1F44" }}>
                Chưa có nhà cung cấp nào
              </p>
              <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
                Thêm nhà cung cấp để bắt đầu quản lý nguyên liệu
              </p>
            </div>
          ) : (
            suppliers.map((s, idx) => {
              const st = STATUS_COLORS[s.status] || STATUS_COLORS.pending;
              return (
                <div
                  key={s.id}
                  className={`rounded-xl p-4 doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                  style={cardStyle}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-full grid place-items-center flex-shrink-0 text-sm font-bold"
                      style={{ background: "#DCE3F0", color: "#102A5C" }}
                    >
                      {s.name[0]?.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span
                          className="text-sm font-semibold"
                          style={{ color: "#0A1F44" }}
                        >
                          {s.name}
                        </span>
                        <span
                          className="text-xs px-2 py-0.5 rounded animate-chip"
                          style={{ background: st.bg, color: st.color }}
                        >
                          {st.label}
                        </span>
                        {s.supplier_type && (
                          <span
                            className="text-xs"
                            style={{ color: "#9CA3AF" }}
                          >
                            {s.supplier_type}
                          </span>
                        )}
                      </div>
                      <p className="text-xs" style={{ color: "#6B7280" }}>
                        {(s as any).tax_code &&
                          `MST: ${(s as any).tax_code} · `}
                        {s.material_count} nguyên liệu · {s.cert_count} chứng
                        chỉ
                        {s.contact_person && ` · ${s.contact_person}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {/* Verify — first, so user sees it before invite */}
                      {s.status !== "verified" && s.cert_count > 0 && (
                        <button
                          onClick={() => verifySupplier(s.id)}
                          title="Xác minh NCC"
                          className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                          style={{
                            background: "#DCE3F0",
                            border: "1px solid #D9B96E",
                          }}
                        >
                          <svg
                            className="w-4 h-4"
                            style={{ color: "#102A5C" }}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                            />
                          </svg>
                        </button>
                      )}
                      {/* Invite NCC */}
                      <button
                        onClick={() => sendInvite(s.id)}
                        title="Gửi yêu cầu hồ sơ"
                        disabled={inviteLoading === s.id}
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#F5F3FF",
                          border: "1px solid #DDD6FE",
                        }}
                      >
                        {inviteLoading === s.id ? (
                          <div className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <svg
                            className="w-4 h-4"
                            style={{ color: "#7C3AED" }}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                            />
                          </svg>
                        )}
                      </button>
                      <button
                        onClick={() => openCerts(s.id)}
                        title="Chứng chỉ"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#FFFBEB",
                          border: "1px solid #FDE68A",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#B45309" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => openSupEdit(s)}
                        title="Sửa"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#F0F9FF",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#0369A1" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => deleteSupplier(s.id)}
                        title="Xoá"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#FEF2F2",
                          border: "1px solid #FECACA",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#DC2626" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* ── Material Form Modal ── */}
      {showMatForm && (
        <Modal onClose={() => setShowMatForm(false)}>
          <div
            className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                {editMat ? "Sửa nguyên liệu" : "Thêm nguyên liệu"}
              </h3>
              <button
                onClick={() => setShowMatForm(false)}
                style={{ color: "#6B7280" }}
              >
                ✕
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Tên nguyên liệu *
                </label>
                <input
                  value={matForm.name}
                  onChange={(e) =>
                    setMatForm((f) => ({ ...f, name: e.target.value }))
                  }
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={inputStyle}
                  placeholder="VD: Bột mì số 11"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Mã SKU
                  </label>
                  <input
                    value={matForm.sku}
                    onChange={(e) =>
                      setMatForm((f) => ({ ...f, sku: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                    placeholder="VD: NL-001"
                  />
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Đơn vị
                  </label>
                  <input
                    value={matForm.unit}
                    onChange={(e) =>
                      setMatForm((f) => ({ ...f, unit: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                    placeholder="kg, lít, cái"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Phân loại
                  </label>
                  <select
                    value={matForm.category}
                    onChange={(e) =>
                      setMatForm((f) => ({ ...f, category: e.target.value, supplier_id: "" }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  >
                    <option value="">Chọn...</option>
                    {CATEGORIES.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Rủi ro Halal
                  </label>
                  <select
                    value={matForm.halal_risk}
                    onChange={(e) =>
                      setMatForm((f) => ({ ...f, halal_risk: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  >
                    {Object.entries(RISK_COLORS).map(([k, v]) => (
                      <option key={k} value={k}>
                        {v.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Nhà cung cấp *
                </label>
                <p className="mb-2 rounded-lg px-3 py-2 text-xs" style={{ background: "#FFFBEB", color: "#92400E" }}>
                  Chỉ NCC có chứng nhận CB đang hiệu lực và đúng phạm vi mới xuất hiện trong danh sách này.
                </p>
                <select
                  value={matForm.supplier_id}
                  onChange={(e) =>
                    setMatForm((f) => ({ ...f, supplier_id: e.target.value }))
                  }
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={inputStyle}
                >
                  <option value="">Chọn nhà cung cấp...</option>
                  {eligibleSuppliers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Mô tả
                </label>
                <textarea
                  value={matForm.description}
                  onChange={(e) =>
                    setMatForm((f) => ({ ...f, description: e.target.value }))
                  }
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-none"
                  style={inputStyle}
                />
              </div>
              <button
                onClick={saveMaterial}
                disabled={matSaving || !matForm.name || !matForm.supplier_id}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{
                  background:
                    !matForm.name || !matForm.supplier_id
                      ? "#E2E8F0"
                      : "#0A1F44",
                  color:
                    !matForm.name || !matForm.supplier_id ? "#9CA3AF" : "#fff",
                }}
              >
                {matSaving
                  ? "Đang lưu..."
                  : editMat
                    ? "Cập nhật"
                    : "Tạo nguyên liệu"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Supplier Form Modal ── */}
      {showSupForm && (
        <Modal onClose={() => setShowSupForm(false)}>
          <div
            className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-5">
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                {editSup ? "Sửa nhà cung cấp" : "Thêm nhà cung cấp"}
              </h3>
              <button
                onClick={() => setShowSupForm(false)}
                style={{ color: "#6B7280" }}
              >
                ✕
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Tên nhà cung cấp *
                </label>
                <input
                  value={supForm.name}
                  onChange={(e) =>
                    setSupForm((f) => ({ ...f, name: e.target.value }))
                  }
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={inputStyle}
                  placeholder="VD: Công ty TNHH Nguyên liệu ABC"
                />
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Mã số thuế
                </label>
                <input
                  value={supForm.tax_code}
                  onChange={(e) =>
                    setSupForm((f) => ({ ...f, tax_code: e.target.value }))
                  }
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={inputStyle}
                  placeholder="VD: 0312345678"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Điện thoại
                  </label>
                  <input
                    value={supForm.phone}
                    onChange={(e) =>
                      setSupForm((f) => ({ ...f, phone: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Email
                  </label>
                  <input
                    value={supForm.email}
                    onChange={(e) =>
                      setSupForm((f) => ({ ...f, email: e.target.value }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  />
                </div>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Địa chỉ
                </label>
                <input
                  value={supForm.address}
                  onChange={(e) =>
                    setSupForm((f) => ({ ...f, address: e.target.value }))
                  }
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                  style={inputStyle}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Người liên hệ
                  </label>
                  <input
                    value={supForm.contact_person}
                    onChange={(e) =>
                      setSupForm((f) => ({
                        ...f,
                        contact_person: e.target.value,
                      }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1"
                    style={{ color: "#6B7280" }}
                  >
                    Loại NCC
                  </label>
                  <input
                    value={supForm.supplier_type}
                    onChange={(e) =>
                      setSupForm((f) => ({
                        ...f,
                        supplier_type: e.target.value,
                      }))
                    }
                    className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                    style={inputStyle}
                    placeholder="VD: Thịt, Gia vị..."
                  />
                </div>
              </div>
              <div>
                <label
                  className="block text-xs font-medium mb-1"
                  style={{ color: "#6B7280" }}
                >
                  Ghi chú
                </label>
                <textarea
                  value={supForm.notes}
                  onChange={(e) =>
                    setSupForm((f) => ({ ...f, notes: e.target.value }))
                  }
                  rows={2}
                  className="w-full px-4 py-2.5 rounded-lg text-sm outline-none resize-none"
                  style={inputStyle}
                />
              </div>

              <button
                onClick={async () => {
                  if (!supForm.name) return;
                  setSupSaving(true);
                  try {
                    // Pydantic Optional[EmailStr] still rejects empty string
                    // (only None passes). Strip empty optional strings to None
                    // so blank fields don't trip server-side validation.
                    const payload: Record<string, unknown> = {
                      ...supForm,
                    };
                    for (const k of Object.keys(payload)) {
                      if (payload[k] === "") payload[k] = null;
                    }
                    const url = editSup
                      ? `/api/api/supply-chain/suppliers/${editSup.id}`
                      : "/api/api/supply-chain/suppliers";
                    await apiFetch(url, {
                      method: editSup ? "PUT" : "POST",
                      token,
                      json: payload,
                      fallbackError: editSup ? "Cập nhật nhà cung cấp thất bại" : "Tạo nhà cung cấp thất bại",
                    });
                    setShowSupForm(false);
                    fetchSuppliers();
                    fetchMaterials();
                  } catch (err) {
                    alert(err instanceof ApiClientError ? err.message : "Lưu nhà cung cấp thất bại");
                  } finally {
                    setSupSaving(false);
                  }
                }}
                disabled={supSaving || !supForm.name}
                className="w-full py-2.5 rounded-xl text-sm font-semibold text-white"
                style={{
                  background: !supForm.name ? "#E2E8F0" : "#0A1F44",
                  color: !supForm.name ? "#9CA3AF" : "#fff",
                }}
              >
                {supSaving
                  ? "Đang lưu..."
                  : editSup
                    ? "Cập nhật"
                    : "Tạo nhà cung cấp"}
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* ── Certificates Modal ── */}
      {certsOpen && (
        <Modal onClose={() => setCertsOpen(null)}>
          <div
            className="w-full max-w-lg rounded-2xl animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              maxHeight: "calc(100vh - 4rem)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="px-6 py-4 flex items-center justify-between"
              style={{ borderBottom: "1px solid #E2E8F0" }}
            >
              <div>
                <h3
                  className="text-base font-bold"
                  style={{ color: "#0A1F44" }}
                >
                  Hồ sơ & Chứng chỉ
                </h3>
                <p className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                  {suppliers.find((s) => s.id === certsOpen)?.name} · Được gửi
                  bởi NCC
                </p>
              </div>
              <button
                onClick={() => setCertsOpen(null)}
                style={{ color: "#6B7280" }}
              >
                ✕
              </button>
            </div>
            <div
              className="px-6 py-4 space-y-2 overflow-y-auto"
              style={{ maxHeight: "calc(100vh - 12rem)" }}
            >
              {certsLoading ? (
                <div className="py-8 flex items-center justify-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
                  <div
                    className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                    style={{ animationDelay: "0.15s" }}
                  />
                  <div
                    className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot"
                    style={{ animationDelay: "0.3s" }}
                  />
                </div>
              ) : certs.length === 0 ? (
                <div className="py-12 text-center animate-scale-in">
                  <p
                    className="text-sm font-medium"
                    style={{ color: "#374151" }}
                  >
                    NCC chưa gửi hồ sơ
                  </p>
                  <p className="text-xs mt-1" style={{ color: "#9CA3AF" }}>
                    Gửi yêu cầu hồ sơ để NCC tự upload chứng chỉ qua portal
                  </p>
                </div>
              ) : (
                certs.map((c, idx) => (
                  <div
                    key={c.id}
                    className={`flex items-center gap-3 px-4 py-3 rounded-xl group animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                    style={{
                      background: "#FFFFFF",
                      border: "1px solid #E2E8F0",
                    }}
                  >
                    <div
                      className="w-10 h-10 rounded-lg grid place-items-center flex-shrink-0"
                      style={{
                        background: "#FFFBEB",
                        border: "1px solid #FDE68A",
                      }}
                    >
                      <svg
                        className="w-5 h-5"
                        style={{ color: "#B45309" }}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="1.8"
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                        />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-sm font-medium truncate"
                        style={{ color: "#0A1F44" }}
                      >
                        {c.original_filename}
                      </p>
                      <p className="text-xs" style={{ color: "#9CA3AF" }}>
                        {CERT_TYPES.find((t) => t.id === c.cert_type)?.label ||
                          c.cert_type}
                        {c.cert_number && ` · ${c.cert_number}`}
                        {c.expiry_date && ` · Hết hạn: ${c.expiry_date}`}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => viewCert(certsOpen!, c.id)}
                        title="Xem"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                        style={{
                          background: "#F0F9FF",
                          border: "1px solid #BAE6FD",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#0369A1" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      </button>
                      <button
                        onClick={() => deleteCert(certsOpen!, c.id)}
                        title="Xoá"
                        className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110 opacity-0 group-hover:opacity-100"
                        style={{
                          background: "#FEF2F2",
                          border: "1px solid #FECACA",
                        }}
                      >
                        <svg
                          className="w-4 h-4"
                          style={{ color: "#DC2626" }}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                          />
                        </svg>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
