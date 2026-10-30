"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useUserAuth } from "@/components/UserAuthContext";
import { parseApiError } from "@/lib/apiError";
import Modal from "@/components/Modal";

interface TemplateItem {
  id?: string;
  code?: string;
  category: string;
  criteria: string;
  severity: "critical" | "major" | "minor";
  clause?: string;
  audit_method?: string;
  documents?: string;
  order_index?: number;
}

interface Template {
  id: string;
  name: string;
  standard: string;
  items: TemplateItem[];
  created_at: string;
}

// Halal Slaughterhouse Checklist — based on TCVN 13710:2023
const DEFAULT_ITEMS_VN: TemplateItem[] = [
  {
    code: "SL01",
    category: "Complete documentation",
    criteria: "Business Registration Certificate, Food Safety Certificate",
    severity: "major",
    audit_method: "Document review",
    documents:
      "Business Registration Certificate, Food Safety Certificate (ATVSTP)",
  },
  {
    code: "SL02",
    category: "Complete documentation",
    criteria:
      "Halal Policy, Halal Manual, Halal Assurance System (HAS) documents",
    severity: "critical",
    clause: "TCVN 13710:2023 4.1.1",
    documents: "Halal Policy, Halal Manual, HAS procedures, flowcharts",
  },
  {
    code: "SL03",
    category: "Complete documentation",
    criteria:
      "Supplier records, traceability records, and employee health records",
    severity: "major",
    documents:
      "Approved supplier list, supplier evaluation records, Traceability procedure, batch records",
  },
  {
    code: "SL04",
    category: "Procurement and receiving",
    criteria:
      "Type and source of animal feed are free from non-halal ingredients",
    severity: "critical",
    clause: "TCVN 13710:2023 4.2.1 - 4.2.4",
    audit_method: "Document review",
    documents: "Feed purchase records, supplier certificates",
  },
  {
    code: "SL05",
    category: "Procurement and receiving",
    criteria: "Has quarantine / veterinary inspection records",
    severity: "major",
    audit_method: "Document review",
    documents: "Quarantine / inspection certificates",
  },
  {
    code: "SL06",
    category: "Procurement and receiving",
    criteria:
      "Location and means of temporary holding while awaiting slaughter",
    severity: "critical",
    clause: "TCVN 13710:2023 4.4.1.3.3 - 4.4.1.3.6",
    audit_method: "On-site observation / Document review",
    documents: "Layout, holding SOP",
  },
  {
    code: "SL07",
    category: "Procurement and receiving",
    criteria:
      "Documented procedures for handling diseased animals or animals that die prior to slaughter",
    severity: "critical",
    clause: "TCVN 13710:2023 4.1.3",
    audit_method: "Document review, Interview",
    documents: "SOP for diseased animals, Disposal records, incident reports",
  },
  {
    code: "SL08",
    category: "Pre-slaughter",
    criteria:
      "Slaughtering location is situated away from contaminated or impure areas",
    severity: "critical",
    clause: "TCVN 13710:2023 4.1.2; 4.5.5",
    audit_method: "On-site observation / Document review",
    documents: "Site layout plan",
  },
  {
    code: "SL09",
    category: "Pre-slaughter",
    criteria: "Animals are clean prior to slaughter",
    severity: "critical",
    clause: "TCVN 13710:2023 4.4.2.1.5, 4.4.2.2.2",
    audit_method: "On-site observation / Document review",
    documents: "Cleaning SOP",
  },
  {
    code: "SL10",
    category: "Pre-slaughter",
    criteria: "Muslim slaughtermen with appropriate competence and experience",
    severity: "critical",
    audit_method: "Interview, Document review",
    documents: "Training records, ID of slaughtermen, or certificate",
  },
  {
    code: "SL11",
    category: "Pre-slaughter",
    criteria: "Presence of qualified Halal supervisors",
    severity: "critical",
    clause: "TCVN 13710:2023 4.4.3.1.4",
    audit_method: "Interview, Document review",
    documents: "Appointment letter, competency records",
  },
  {
    code: "SL12",
    category: "Pre-slaughter",
    criteria:
      "Sufficient number of personnel appropriate to the number of animals slaughtered",
    severity: "critical",
    clause: "TCVN 13710:2023 4.5.3",
    audit_method: "Interview",
  },
  {
    code: "SL13",
    category: "Pre-slaughter",
    criteria: "Adequate and clean equipment",
    severity: "major",
    clause: "TCVN 13710:2023 4.5.4.1 - 4.5.4.5",
    audit_method: "On-site observation / Document review",
    documents: "Equipment cleaning logs",
  },
  {
    code: "SL14",
    category: "Pre-slaughter",
    criteria: "Knives meeting required standards",
    severity: "major",
    clause: "TCVN 13710:2023 4.5.4.1, 4.5.4.2",
    audit_method: "On-site observation",
  },
  {
    code: "SL15",
    category: "During slaughter",
    criteria:
      "Manual slaughter, one animal at a time, using the right hand, performed swiftly",
    severity: "critical",
    clause: "TCVN 13710:2023 4.5.1",
    audit_method: "On-site observation / Document review",
    documents: "Slaughter SOP",
  },
  {
    code: "SL16",
    category: "During slaughter",
    criteria: "Halal supervisor oversees the entire slaughtering process",
    severity: "critical",
    documents: "Supervisor record",
  },
  {
    code: "SL17",
    category: "During slaughter",
    criteria:
      "Proper separation of internal organs to prevent contamination of the meat",
    severity: "critical",
    documents: "Evisceration SOP",
  },
  {
    code: "SL18",
    category: "Post-slaughter",
    criteria:
      "Wastewater, manure, blood, and by-products treatment system in place",
    severity: "major",
    clause: "TCVN 13710:2023 4.6.2",
    audit_method: "Document review",
    documents: "Waste treatment SOP, contracts",
  },
  {
    code: "SL19",
    category: "Post-slaughter",
    criteria:
      "Records and procedures for post-slaughter handling and maintenance",
    severity: "critical",
    clause: "TCVN 13710:2023 4.6.1.2, 4.6.1.4, 4.8",
    audit_method: "Document review",
    documents: "Post-slaughter SOP, Sanitation schedules",
  },
  {
    code: "SL20",
    category: "Packaging and labeling",
    criteria:
      "Products are packaged using clean materials free from najis contamination",
    severity: "critical",
    clause: "TCVN 13710:2023 4.7.1 - 4.7.2",
    audit_method: "Document review",
    documents: "Packaging material specifications",
  },
  {
    code: "SL21",
    category: "Packaging and labeling",
    criteria: "Packaging area is clean and hygienic",
    severity: "major",
    audit_method: "On-site observation / Document review",
    documents: "Cleaning logs",
  },
  {
    code: "SL22",
    category: "Packaging and labeling",
    criteria: "Labels are complete and compliant with applicable regulations",
    severity: "major",
    audit_method: "On-site observation / Document review",
    documents: "Label samples, labeling SOP",
  },
  {
    code: "SL23",
    category: "Storage",
    criteria:
      "Meat products and by-products are segregated from non-Halal products",
    severity: "critical",
    clause: "TCVN 13710:2023 4.7.3",
    audit_method: "On-site observation / Document review",
    documents: "Storage layout",
  },
  {
    code: "SL24",
    category: "Storage",
    criteria: "Storage temperature requirements are properly controlled",
    severity: "major",
    audit_method: "On-site observation / Document review",
    documents: "Temperature logs",
  },
  {
    code: "SL25",
    category: "Storage",
    criteria: "No animals in storage",
    severity: "major",
    audit_method: "On-site observation",
  },
  {
    code: "SL26",
    category: "Transportation",
    criteria: "Dedicated transportation vehicles that are clean and hygienic",
    severity: "major",
    clause: "TCVN 13710:2023 4.7.4",
    audit_method: "On-site observation / Document review",
    documents: "Vehicle inspection / cleaning records",
  },
  {
    code: "SL27",
    category: "Human resources",
    criteria: "Staff competency",
    severity: "major",
    audit_method: "Interview, Document review",
    documents: "Training records",
  },
  {
    code: "SL28",
    category: "Human resources",
    criteria: "Prayer area availability",
    severity: "major",
    clause: "TCVN 13710:2023 4.1.5",
  },
  {
    code: "SL29",
    category: "Human resources",
    criteria: "Accessibility for Muslim staff",
    severity: "critical",
    clause: "TCVN 13710:2023 4.1.5",
    audit_method: "Interview, Document review",
    documents: "Halal Policy, Internal Policy",
  },
];

export default function AuditTemplatesPage() {
  const router = useRouter();
  const { user, token, isAuthenticated, loading } = useUserAuth();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [fetching, setFetching] = useState(false);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formStandard, setFormStandard] = useState("");
  const [formItems, setFormItems] = useState<TemplateItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [seeding, setSeeding] = useState(false);

  useEffect(() => {
    if (
      !loading &&
      (!isAuthenticated || user?.role !== "provider" || !user?.is_owner)
    )
      router.replace(
        user?.role === "provider" ? "/dashboard/provider" : "/provider/login",
      );
  }, [loading, isAuthenticated, user, router]);

  const fetchTemplates = useCallback(async () => {
    if (!token) return;
    setFetching(true);
    try {
      const res = await fetch("/api/api/audits/templates", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTemplates(Array.isArray(data) ? data : data.templates || []);
      }
    } finally {
      setFetching(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAuthenticated) fetchTemplates();
  }, [isAuthenticated, fetchTemplates]);

  const openCreate = () => {
    setEditingId(null);
    setFormName("");
    setFormStandard("");
    setFormItems([{ category: "", criteria: "", severity: "major" }]);
    setSaveError("");
    setShowModal(true);
  };

  const openEdit = (t: Template) => {
    setEditingId(t.id);
    setFormName(t.name);
    setFormStandard(t.standard);
    setFormItems(
      t.items.length > 0
        ? t.items.map((i) => ({ ...i }))
        : [{ category: "", criteria: "", severity: "major" }],
    );
    setSaveError("");
    setShowModal(true);
  };

  const addItem = () => {
    setFormItems((prev) => [
      ...prev,
      { category: "", criteria: "", severity: "major" },
    ]);
  };

  const removeItem = (idx: number) => {
    setFormItems((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateItem = (
    idx: number,
    field: keyof TemplateItem,
    value: string,
  ) => {
    setFormItems((prev) =>
      prev.map((item, i) => (i === idx ? { ...item, [field]: value } : item)),
    );
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError("");
    setSaving(true);
    try {
      const payload = {
        name: formName,
        standard: formStandard,
        items: formItems.map((item, idx) => ({
          category: item.category,
          criteria: item.criteria,
          severity: item.severity,
          order_index: idx,
        })),
      };
      const url = editingId
        ? `/api/api/audits/templates/${editingId}`
        : "/api/api/audits/templates";
      const res = await fetch(url, {
        method: editingId ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, "L\u01b0u th\u1ea5t b\u1ea1i"));
      }
      setShowModal(false);
      fetchTemplates();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "L\u1ed7i");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("X\u00e1c nh\u1eadn xo\u00e1 template n\u00e0y?")) return;
    try {
      await fetch(`/api/api/audits/templates/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchTemplates();
    } catch {
      /* ignore */
    }
  };

  const handleSeedDefault = async () => {
    setSeeding(true);
    try {
      const payload = {
        name: "Halal Slaughterhouse Checklist — TCVN 13710:2023",
        standard: "TCVN 13710:2023",
        items: DEFAULT_ITEMS_VN.map((item, idx) => ({
          code: item.code || "",
          category: item.category,
          criteria: item.criteria,
          severity: item.severity,
          clause: item.clause || "",
          audit_method: item.audit_method || "",
          documents: item.documents || "",
          order_index: idx,
        })),
      };
      const res = await fetch("/api/api/audits/templates", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(parseApiError(err, "T\u1ea1o template th\u1ea5t b\u1ea1i"));
        return;
      }
      fetchTemplates();
    } finally {
      setSeeding(false);
    }
  };

  if (loading || !user)
    return (
      <div className="grid place-items-center min-h-[60vh]">
        <div className="flex items-center gap-1.5">
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
      </div>
    );

  return (
    <div
      className="flex flex-col flex-1 lg:min-h-0 w-full overflow-x-hidden"
      data-page
    >
      {/* Header */}
      <div
        className="rounded-2xl p-6 mb-6 animate-section"
        style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
      >
        <div
          className="grid items-center"
          style={{ gridTemplateColumns: "1fr auto" }}
        >
          <div className="grid grid-flow-col items-center gap-3 justify-start">
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
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
                Checklist Template
              </h1>
              <p className="text-sm" style={{ color: "#6B7280" }}>
                {templates.length} template · {user.company_name}
              </p>
            </div>
          </div>
          <button
            onClick={openCreate}
            className="grid items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
            style={{
              gridTemplateColumns: "auto 1fr",
              background: "#0A1F44",
              boxShadow: "0 4px 12px rgba(10,31,68,0.3)",
            }}
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.5"
                d="M12 4v16m8-8H4"
              />
            </svg>
            T\u1ea1o Template
          </button>
        </div>
      </div>

      {/* Template list */}
      <div className="flex-1 lg:min-h-0 lg:overflow-y-auto space-y-3">
        {fetching ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div
                key={i}
                className="rounded-2xl h-24 animate-pulse"
                style={{ background: "#F5F1E8", opacity: 1 - i * 0.2 }}
              />
            ))}
          </div>
        ) : templates.length === 0 ? (
          <div
            className="rounded-2xl p-12 text-center animate-section"
            style={{ background: "#F5F1E8", border: "1px solid #E2E8F0" }}
          >
            <svg
              className="w-14 h-14 mx-auto mb-4"
              style={{ color: "#D1D5DB" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
              />
            </svg>
            <p className="font-semibold mb-2" style={{ color: "#0A1F44" }}>
              Ch\u01b0a c\u00f3 template n\u00e0o
            </p>
            <p className="text-sm mb-5" style={{ color: "#6B7280" }}>
              T\u1ea1o template checklist \u0111\u1ec3 s\u1eed d\u1ee5ng trong
              c\u00e1c \u0111\u1ee3t \u0111\u00e1nh gi\u00e1
            </p>
            <button
              onClick={handleSeedDefault}
              disabled={seeding}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
              style={{
                background: seeding ? "#E2E8F0" : "#0A1F44",
                color: seeding ? "#6B7280" : "white",
                boxShadow: seeding ? "none" : "0 4px 12px rgba(10,31,68,0.3)",
              }}
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"
                />
              </svg>
              {seeding ? "Đang tạo..." : "Tạo template mẫu TCVN 13710:2023"}
            </button>
          </div>
        ) : (
          templates.map((t, idx) => {
            const itemCount = t.items?.length || 0;
            const categories = [
              ...new Set((t.items || []).map((i) => i.category)),
            ];
            return (
              <div
                key={t.id}
                className={`rounded-xl p-5 transition-colors doc-card-hover animate-list-item stagger-${Math.min(idx + 1, 12)}`}
                style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
              >
                <div
                  className="grid items-start gap-3"
                  style={{ gridTemplateColumns: "auto 1fr auto" }}
                >
                  {/* Icon */}
                  <div
                    className="w-10 h-10 rounded-xl grid place-items-center"
                    style={{
                      background: "rgba(10,31,68,0.1)",
                      border: "1px solid rgba(10,31,68,0.2)",
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
                        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                      />
                    </svg>
                  </div>
                  {/* Info */}
                  <div className="min-w-0">
                    <p
                      className="text-sm font-semibold"
                      style={{ color: "#0A1F44" }}
                    >
                      {t.name}
                    </p>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span
                        className="px-2.5 py-0.5 rounded-lg text-xs font-medium"
                        style={{
                          background: "rgba(10,31,68,0.08)",
                          color: "#0A1F44",
                          border: "1px solid rgba(10,31,68,0.2)",
                        }}
                      >
                        {t.standard}
                      </span>
                      <span className="text-xs" style={{ color: "#6B7280" }}>
                        {itemCount} ti\u00eau ch\u00ed
                      </span>
                      <span className="text-xs" style={{ color: "#9CA3AF" }}>
                        {categories.length} danh m\u1ee5c
                      </span>
                    </div>
                    {categories.length > 0 && (
                      <div className="flex items-center gap-1 mt-2 flex-wrap">
                        {categories.slice(0, 5).map((cat) => (
                          <span
                            key={cat}
                            className="px-2 py-0.5 rounded text-xs"
                            style={{
                              background: "#F5F1E8",
                              color: "#6B7280",
                              border: "1px solid #E2E8F0",
                            }}
                          >
                            {cat}
                          </span>
                        ))}
                        {categories.length > 5 && (
                          <span
                            className="text-xs"
                            style={{ color: "#9CA3AF" }}
                          >
                            +{categories.length - 5}
                          </span>
                        )}
                      </div>
                    )}
                    <p className="text-xs mt-2" style={{ color: "#9CA3AF" }}>
                      T\u1ea1o:{" "}
                      {new Date(t.created_at).toLocaleDateString("vi-VN")}
                    </p>
                  </div>
                  {/* Actions */}
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => openEdit(t)}
                      title="S\u1eeda"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "rgba(14,165,233,0.1)",
                        border: "1px solid rgba(14,165,233,0.2)",
                      }}
                    >
                      <svg
                        className="w-4 h-4"
                        style={{ color: "#0EA5E9" }}
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
                      onClick={() => handleDelete(t.id)}
                      title="Xo\u00e1"
                      className="w-8 h-8 rounded-lg grid place-items-center transition-all duration-200 ease-out hover:scale-110"
                      style={{
                        background: "rgba(239,68,68,0.08)",
                        border: "1px solid rgba(239,68,68,0.15)",
                      }}
                    >
                      <svg
                        className="w-4 h-4"
                        style={{ color: "#6B7280" }}
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

      {/* Create/Edit Modal */}
      {showModal && (
        <Modal onClose={() => setShowModal(false)}>
          <div
            className="w-full max-w-2xl rounded-2xl animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 25px 60px rgba(0,0,0,0.15)",
              maxHeight: "calc(100vh - 4rem)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              className="px-6 py-4 flex items-center justify-between"
              style={{ borderBottom: "1px solid #E2E8F0" }}
            >
              <h3 className="text-base font-bold" style={{ color: "#0A1F44" }}>
                {editingId
                  ? "Ch\u1ec9nh s\u1eeda Template"
                  : "T\u1ea1o Template m\u1edbi"}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="w-8 h-8 rounded-lg grid place-items-center"
                style={{ background: "rgba(0,0,0,0.05)" }}
              >
                <span style={{ color: "#6B7280" }}>{"\u2715"}</span>
              </button>
            </div>

            {/* Modal Body */}
            <form
              onSubmit={handleSave}
              className="overflow-y-auto"
              style={{ maxHeight: "calc(100vh - 14rem)" }}
            >
              <div className="px-6 py-4 space-y-4">
                {/* Name + Standard */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label
                      className="block text-xs font-medium mb-1.5"
                      style={{ color: "#6B7280" }}
                    >
                      T\u00ean template *
                    </label>
                    <input
                      type="text"
                      required
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                      placeholder="VD: Checklist MS 1500"
                      className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                      style={{
                        background: "#FFFFFF",
                        border: "1px solid #E2E8F0",
                        color: "#0A1F44",
                      }}
                    />
                  </div>
                  <div>
                    <label
                      className="block text-xs font-medium mb-1.5"
                      style={{ color: "#6B7280" }}
                    >
                      Ti\u00eau chu\u1ea9n *
                    </label>
                    <input
                      type="text"
                      required
                      value={formStandard}
                      onChange={(e) => setFormStandard(e.target.value)}
                      placeholder="VD: MS 1500:2019"
                      className="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
                      style={{
                        background: "#FFFFFF",
                        border: "1px solid #E2E8F0",
                        color: "#0A1F44",
                      }}
                    />
                  </div>
                </div>

                {/* Divider */}
                <div style={{ borderTop: "1px solid #E2E8F0" }} />

                {/* Items */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <label
                      className="text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      Ti\u00eau ch\u00ed \u0111\u00e1nh gi\u00e1 (
                      {formItems.length})
                    </label>
                    <button
                      type="button"
                      onClick={addItem}
                      className="inline-flex items-center gap-1 px-3 py-1 rounded-lg text-xs font-medium transition-all duration-200 ease-out hover:scale-105"
                      style={{
                        background: "#DCE3F0",
                        color: "#0A1F44",
                        border: "1px solid #D9B96E",
                      }}
                    >
                      <svg
                        className="w-3 h-3"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2.5"
                          d="M12 4v16m8-8H4"
                        />
                      </svg>
                      Th\u00eam ti\u00eau ch\u00ed
                    </button>
                  </div>

                  <div className="space-y-3">
                    {formItems.map((item, idx) => (
                      <div
                        key={idx}
                        className="rounded-xl p-4"
                        style={{
                          background: "#FFFFFF",
                          border: "1px solid #E2E8F0",
                        }}
                      >
                        <div className="flex items-start gap-3">
                          {/* Order number */}
                          <div
                            className="w-6 h-6 rounded-full grid place-items-center flex-shrink-0 mt-1 text-xs font-bold"
                            style={{ background: "#E2E8F0", color: "#6B7280" }}
                          >
                            {idx + 1}
                          </div>
                          <div className="flex-1 space-y-2">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                              <input
                                value={item.category}
                                onChange={(e) =>
                                  updateItem(idx, "category", e.target.value)
                                }
                                placeholder="Danh m\u1ee5c (VD: Nguy\u00ean li\u1ec7u)"
                                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                                style={{
                                  background: "#FFFFFF",
                                  border: "1px solid #E2E8F0",
                                  color: "#0A1F44",
                                }}
                              />
                              <select
                                value={item.severity}
                                onChange={(e) =>
                                  updateItem(idx, "severity", e.target.value)
                                }
                                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                                style={{
                                  background: "#FFFFFF",
                                  border: "1px solid #E2E8F0",
                                  color: "#0A1F44",
                                }}
                              >
                                <option value="critical">
                                  Nghi\u00eam tr\u1ecdng (Critical)
                                </option>
                                <option value="major">
                                  Ch\u00ednh (Major)
                                </option>
                                <option value="minor">Ph\u1ee5 (Minor)</option>
                              </select>
                            </div>
                            <textarea
                              value={item.criteria}
                              onChange={(e) =>
                                updateItem(idx, "criteria", e.target.value)
                              }
                              placeholder="Ti\u00eau ch\u00ed \u0111\u00e1nh gi\u00e1..."
                              rows={2}
                              className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
                              style={{
                                background: "#FFFFFF",
                                border: "1px solid #E2E8F0",
                                color: "#0A1F44",
                              }}
                            />
                          </div>
                          {/* Delete item */}
                          {formItems.length > 1 && (
                            <button
                              type="button"
                              onClick={() => removeItem(idx)}
                              className="w-7 h-7 rounded-lg grid place-items-center flex-shrink-0 mt-1 transition-all duration-200 ease-out hover:scale-110"
                              style={{
                                background: "rgba(239,68,68,0.08)",
                                border: "1px solid rgba(239,68,68,0.15)",
                              }}
                            >
                              <svg
                                className="w-3.5 h-3.5"
                                style={{ color: "#DC2626" }}
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth="2.5"
                                  d="M6 18L18 6M6 6l12 12"
                                />
                              </svg>
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {saveError && (
                  <p className="text-xs text-red-400">{saveError}</p>
                )}
              </div>

              {/* Modal Footer */}
              <div
                className="px-6 py-4 flex items-center justify-end gap-3"
                style={{ borderTop: "1px solid #E2E8F0" }}
              >
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all"
                  style={{ color: "#6B7280", border: "1px solid #E2E8F0" }}
                >
                  Hu\u1ef7
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all duration-200 ease-out hover:scale-105"
                  style={{
                    background: saving ? "#E2E8F0" : "#0A1F44",
                    color: saving ? "#6B7280" : "white",
                    boxShadow: saving
                      ? "none"
                      : "0 4px 12px rgba(10,31,68,0.3)",
                  }}
                >
                  {saving
                    ? "\u0110ang l\u01b0u..."
                    : editingId
                      ? "C\u1eadp nh\u1eadt"
                      : "T\u1ea1o Template"}
                </button>
              </div>
            </form>
          </div>
        </Modal>
      )}
    </div>
  );
}
