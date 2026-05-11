"use client";

import { useState, useEffect, useCallback } from "react";
import { useUserAuth } from "@/components/UserAuthContext";
import { useFeatureFlags } from "@/lib/featureFlags";
import { downloadPdfHtml, RenderPdfError } from "@/lib/renderPdfHtml";
import Link from "next/link";

// ─── Types ───────────────────────────────────────────────────────────────────

interface TemplateInfo {
  doc_type: string;
  label: string;
  has_vi: boolean;
  has_en: boolean;
  vi_size: number | null;
  en_size: number | null;
}

interface CompanyProfile {
  company_name: string;
  email: string;
  address: string | null;
  phone: string | null;
  representative_name: string | null;
  manager_name: string | null;
}

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
  icon: string | null;
  available_standards: StandardSummary[];
}

interface StandardDetail {
  id: string;
  code: string;
  name_vi: string;
  organization: string | null;
  scheme_version: string | null;
  doc_types: Array<{ doc_type: string; required: boolean; display_order: number }>;
}

const INDUSTRY_ICON_MAP: Record<string, string> = {
  factory: "🏭",
  restaurant: "🏨",
  cow: "🐄",
  pharmacy: "💊",
  cosmetic: "💄",
  truck: "🚛",
};

// ─── Main ────────────────────────────────────────────────────────────────────

export default function CreateDocumentPage() {
  const { user, token, isAuthenticated } = useUserAuth();

  const [step, setStep] = useState(1);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [industry, setIndustry] = useState<IndustrySchemaSummary | null>(null);
  const [standard, setStandard] = useState<StandardDetail | null>(null);
  const [selectedStandardCode, setSelectedStandardCode] = useState<string | null>(null);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState(false);
  const [error, setError] = useState("");
  const [lang, setLang] = useState<"vi" | "en">("vi");
  const [outputFormat, setOutputFormat] = useState<"docx" | "pdf">("docx");

  // Multi-doc_type PDF flag check via the FeatureFlagProvider context map.
  // We avoid one useFeature() per doc_type (hook order would explode as
  // more templates ship in Phase 2+).
  const { flags: featureFlags } = useFeatureFlags();
  const isPdfEnabledFor = useCallback(
    (docType: string) =>
      featureFlags[`pdf_html_renderer_v1.${docType}`] === true,
    [featureFlags],
  );
  // Coverage map: doc_type → { coverage_pct, filled, total }
  const [coverageMap, setCoverageMap] = useState<
    Record<string, { coverage_pct: number; filled: number; total: number }>
  >({});
  const [allPlaceholders, setAllPlaceholders] = useState<
    Array<{
      key: string;
      source: string | null;
      default_value: string | null;
      is_system: boolean;
    }>
  >([]);

  // ── Fetch templates + company profile ────────────────────────────────────

  useEffect(() => {
    if (!isAuthenticated || !token) return;

    const fetchData = async () => {
      setLoading(true);
      try {
        const [tplRes, profileRes, phRes, industryRes] = await Promise.all([
          fetch("/api/templates/available"),
          fetch("/api/auth/company-profile", {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch("/api/placeholders"),
          user?.industry_schema_code
            ? fetch(`/api/industry-schemas/${user.industry_schema_code}`, {
                headers: { Authorization: `Bearer ${token}` },
              })
            : Promise.resolve(null),
        ]);

        if (tplRes.ok) {
          const data = await tplRes.json();
          setTemplates(data.templates || []);
        }

        if (profileRes.ok) {
          setProfile(await profileRes.json());
        }

        if (phRes.ok) {
          const phData = await phRes.json();
          setAllPlaceholders(phData.placeholders || []);
        }

        if (industryRes && industryRes.ok) {
          const industryData: IndustrySchemaSummary = await industryRes.json();
          setIndustry(industryData);
          // Auto-select default standard if exactly 1 available, else pre-select default
          if (industryData.available_standards.length > 0) {
            const def = industryData.available_standards.find((s) => s.is_default);
            const auto = def ?? industryData.available_standards[0];
            setSelectedStandardCode(auto.code);
          }
        }
      } catch {
        setError("Không thể tải dữ liệu");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [isAuthenticated, token, user?.industry_schema_code]);

  // Fetch standard detail (doc_types list) when user picks a standard
  useEffect(() => {
    if (!token || !selectedStandardCode) {
      setStandard(null);
      return;
    }
    (async () => {
      const res = await fetch(`/api/standard-types/${selectedStandardCode}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setStandard(await res.json());
    })();
  }, [token, selectedStandardCode]);

  // Fetch coverage map for templates in current standard (parallel)
  useEffect(() => {
    if (!token || !standard?.doc_types?.length) {
      setCoverageMap({});
      return;
    }
    (async () => {
      const results = await Promise.all(
        standard.doc_types.map(async (dt) => {
          try {
            const r = await fetch(
              `/api/api/templates/${dt.doc_type}/placeholder-coverage`,
              { headers: { Authorization: `Bearer ${token}` } },
            );
            if (!r.ok) return [dt.doc_type, null] as const;
            const b = await r.json();
            return [
              dt.doc_type,
              {
                coverage_pct: b.coverage_pct,
                filled: b.filled,
                total: b.total_fields,
              },
            ] as const;
          } catch {
            return [dt.doc_type, null] as const;
          }
        }),
      );
      const map: Record<string, { coverage_pct: number; filled: number; total: number }> = {};
      for (const [k, v] of results) {
        if (v) map[k] = v;
      }
      setCoverageMap(map);
    })();
  }, [token, standard]);

  // ── Toggle template selection — uncapped (was max 3) ─────────────────────

  const toggleTemplate = (docType: string) => {
    setSelectedTypes((prev) => {
      if (prev.includes(docType)) return prev.filter((t) => t !== docType);
      return [...prev, docType];
    });
  };

  // ── Check if profile is complete ─────────────────────────────────────────

  const profileComplete = !!(
    profile?.company_name &&
    profile?.representative_name &&
    profile?.address
  );

  // ── Generate DOCX files ──────────────────────────────────────────────────

  const generateDocx = useCallback(
    async (docType: string) => {
      const Docxtemplater = (await import("docxtemplater")).default;
      const PizZip = (await import("pizzip")).default;
      const { saveAs } = await import("file-saver");

      // Cache-bust to ensure latest template content (admin may have rotated it).
      // Browsers + service workers must not return stale copies on doc generation.
      const res = await fetch(
        `/api/templates/${docType}/download?lang=${lang}&_t=${Date.now()}`,
        {
          headers: { Authorization: `Bearer ${token}` },
          cache: "no-store",
        },
      );
      if (!res.ok) throw new Error(`Template "${docType}" chưa được upload`);

      const arrayBuffer = await res.arrayBuffer();
      const zip = new PizZip(arrayBuffer);

      // Fix Word XML splitting placeholders across runs
      for (const fileName of [
        "word/document.xml",
        "word/header1.xml",
        "word/header2.xml",
        "word/footer1.xml",
        "word/footer2.xml",
      ]) {
        const file = zip.file(fileName);
        if (!file) continue;
        let xml = file.asText();
        xml = xml.replace(
          /<\/w:t><\/w:r><w:r>(?:<w:rPr>(?:<[^>]*\/?>)*<\/w:rPr>)?<w:t(?:\s[^>]*)?>/g,
          "",
        );
        xml = xml.replace(/\{\{([a-z_]+)\)/g, "{{$1}}");
        xml = xml.replace(/\{\{([a-z_]+)\}(?!\})/g, "{{$1}}");
        zip.file(fileName, xml);
      }

      const doc = new Docxtemplater(zip, {
        paragraphLoop: true,
        linebreaks: true,
        delimiters: { start: "{{", end: "}}" },
        nullGetter: () => "", // Unknown placeholders → empty string instead of error
      });

      const now = new Date();
      const dateStr = now.toLocaleDateString("vi-VN", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });

      // Build data from all placeholders using source mapping
      const profileMap: Record<string, string> = {
        company_name: profile?.company_name || "",
        representative_name: profile?.representative_name || "",
        address: profile?.address || "",
        phone: profile?.phone || "",
        email: profile?.email || "",
        manager_name: profile?.manager_name || "",
      };
      const autoMap: Record<string, string> = {
        "auto:date": dateStr,
        "auto:year": String(now.getFullYear()),
        "auto:month": String(now.getMonth() + 1),
        "auto:day": String(now.getDate()),
      };

      const data: Record<string, string> = {};

      // If allPlaceholders loaded from API, use dynamic resolution
      if (allPlaceholders.length > 0) {
        for (const p of allPlaceholders) {
          if (p.source && p.source.startsWith("auto:")) {
            data[p.key] = autoMap[p.source] || "";
          } else if (p.source && profileMap[p.source] !== undefined) {
            data[p.key] = profileMap[p.source];
          } else if (p.default_value) {
            data[p.key] = p.default_value;
          } else {
            data[p.key] = "";
          }
        }
      } else {
        // Fallback: hardcode system placeholders if API failed
        Object.assign(data, {
          ten_cong_ty: profileMap.company_name,
          ten_giam_doc: profileMap.representative_name,
          dia_chi: profileMap.address,
          dien_thoai: profileMap.phone,
          email: profileMap.email,
          nguoi_quan_ly: profileMap.manager_name,
          ngay_tao: autoMap["auto:date"],
          nam: autoMap["auto:year"],
          thang: autoMap["auto:month"],
          ngay: autoMap["auto:day"],
        });
      }

      // Also fetch placeholders at render time if empty (race condition fix)
      if (allPlaceholders.length === 0) {
        try {
          const phRes = await fetch("/api/placeholders");
          if (phRes.ok) {
            const phData = await phRes.json();
            for (const p of phData.placeholders || []) {
              if (data[p.key] !== undefined) continue; // already set by fallback
              if (p.source && p.source.startsWith("auto:")) {
                data[p.key] = autoMap[p.source] || "";
              } else if (p.source && profileMap[p.source] !== undefined) {
                data[p.key] = profileMap[p.source];
              } else if (p.default_value) {
                data[p.key] = p.default_value;
              } else {
                data[p.key] = "";
              }
            }
          }
        } catch {}
      }

      doc.setData(data);

      doc.render();

      const blob = doc.getZip().generate({
        type: "blob",
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });

      const safeName = (profile?.company_name || "company").replace(
        /\s+/g,
        "_",
      );
      saveAs(blob, `${docType}_${safeName}.docx`);
    },
    [token, profile, lang, allPlaceholders],
  );

  // ── Build minimal payload per doc_type ─────────────────────────────────
  //
  // Every Pydantic schema requires at minimum {business_name, issued_date}
  // (+ effective_date for SOPs / halal_policy / has_manual). The 3-stage
  // backend pipeline (aggregator + filter) merges company DB data and
  // admin_templates JSON cfg on top, so the frontend only needs to send
  // what it has. Rich free-form fields (clauses, chapters, procedure
  // steps) come from admin-uploaded DOCX content via the aggregator —
  // not from the frontend.
  const buildPdfData = useCallback(
    (docType: string): Record<string, unknown> | null => {
      const today = new Date().toISOString().slice(0, 10);
      const businessName = profile?.company_name?.trim();
      if (!businessName) return null;

      // company_profile passes through extra fields that the frontend
      // does collect (address, phone, email, representative).
      if (docType === "company_profile") {
        return {
          business_name: businessName,
          address: profile?.address || undefined,
          representative: profile?.representative_name || undefined,
          phone: profile?.phone || undefined,
          email: profile?.email || undefined,
          issued_date: today,
        };
      }

      // 6× SOP variants — same SopData schema; admin cfg fills the rest.
      if (docType.startsWith("sop_")) {
        return {
          business_name: businessName,
          effective_date: today,
          issued_date: today,
        };
      }

      // halal_policy: halal_commitment is a required non-empty string —
      // we provide a generic boilerplate that admin can override via
      // admin_templates/halal_policy.json (cfg.defaults.halal_commitment)
      // if they want their own wording.
      if (docType === "halal_policy") {
        return {
          business_name: businessName,
          halal_commitment:
            `Chúng tôi — Ban lãnh đạo ${businessName} — cam kết tuyệt đối tuân thủ tiêu chuẩn Halal MS 1500:2019 trong mọi sản phẩm và hoạt động sản xuất, từ nguyên liệu đầu vào đến sản phẩm cuối tới tay người tiêu dùng.`,
          effective_date: today,
          issued_date: today,
        };
      }

      // has_manual + halal_manual share schema (HasManualData).
      if (docType === "has_manual" || docType === "halal_manual") {
        return {
          business_name: businessName,
          effective_date: today,
          issued_date: today,
        };
      }

      // Doc type not yet wired to HTML renderer → caller falls back to DOCX.
      return null;
    },
    [profile],
  );

  const generatePdfFallbackDocx = useCallback(
    async (docType: string) => {
      const data = buildPdfData(docType);
      if (!data || !token) {
        await generateDocx(docType);
        return;
      }
      const safeName = (profile?.company_name || "company").replace(/\s+/g, "_");
      try {
        await downloadPdfHtml({
          docType,
          data,
          title: profile?.company_name
            ? `${profile.company_name} — Hồ sơ doanh nghiệp`
            : undefined,
          isDraft: true,
          lang,
          token,
          filename: `${docType}_${safeName}.pdf`,
        });
      } catch (err) {
        // 404 (flag off / template not implemented) or 501 → silent fallback
        // to DOCX so the user always gets a file. Other errors propagate.
        if (
          err instanceof RenderPdfError &&
          (err.status === 404 || err.status === 501)
        ) {
          await generateDocx(docType);
          return;
        }
        throw err;
      }
    },
    [buildPdfData, generateDocx, profile, lang, token],
  );

  const handleGenerate = async () => {
    setGenerating(true);
    setError("");
    setGenerated(false);
    try {
      for (const docType of selectedTypes) {
        if (outputFormat === "pdf") {
          await generatePdfFallbackDocx(docType);
        } else {
          await generateDocx(docType);
        }
      }
      setGenerated(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Lỗi khi tạo tài liệu");
    } finally {
      setGenerating(false);
    }
  };

  // ── Guards ───────────────────────────────────────────────────────────────

  if (!isAuthenticated) {
    return (
      <div
        className="min-h-screen grid place-items-center"
        style={{ background: "#FFFFFF" }}
      >
        <div className="text-center space-y-4">
          <p style={{ color: "#6B7280" }}>
            Vui lòng đăng nhập để sử dụng chức năng này
          </p>
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

  if (user?.role !== "business") {
    return (
      <div
        className="min-h-screen grid place-items-center"
        style={{ background: "#FFFFFF" }}
      >
        <p style={{ color: "#6B7280" }}>
          Chức năng này chỉ dành cho tài khoản doanh nghiệp
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        className="min-h-screen grid place-items-center"
        style={{ background: "#FFFFFF" }}
      >
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
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  const profileRows = [
    { label: "Tên công ty", value: profile?.company_name, key: "ten_cong_ty" },
    {
      label: "Giám đốc / Đại diện",
      value: profile?.representative_name,
      key: "ten_giam_doc",
    },
    { label: "Địa chỉ", value: profile?.address, key: "dia_chi" },
    { label: "Điện thoại", value: profile?.phone, key: "dien_thoai" },
    { label: "Email", value: profile?.email, key: "email" },
    {
      label: "Người quản lý HT",
      value: profile?.manager_name,
      key: "nguoi_quan_ly",
    },
  ];

  const now = new Date();
  const dateStr = now.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen" style={{ background: "#FFFFFF" }} data-page>
      <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div className="animate-section">
          <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
            Tạo hồ sơ theo đúng chuẩn
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            Chọn mẫu tài liệu Halal, hệ thống tự động điền thông tin doanh
            nghiệp và tải về file DOCX
          </p>
        </div>

        {/* TASK #19 — Industry + Standard chooser */}
        {industry && (
          <div
            className="rounded-2xl p-4 animate-section space-y-3"
            style={{
              background: "rgba(10,31,68,0.04)",
              border: "1px solid #E2E8F0",
            }}
            data-testid="industry-context-badge"
          >
            <div className="flex items-center gap-3">
              <div className="text-3xl leading-none">
                {INDUSTRY_ICON_MAP[industry.icon ?? ""] ?? "📋"}
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold" style={{ color: "#0A1F44" }}>
                  Ngành: {industry.name_vi}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "#6B7280" }}>
                  Chọn tiêu chuẩn cho hồ sơ này:
                </div>
              </div>
              <Link
                href="/settings/company"
                className="text-xs underline"
                style={{ color: "#6B7280" }}
              >
                Đổi ngành
              </Link>
            </div>

            {industry.available_standards.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {industry.available_standards.map((s) => {
                  const sel = selectedStandardCode === s.code;
                  return (
                    <button
                      key={s.code}
                      type="button"
                      onClick={() => setSelectedStandardCode(s.code)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium"
                      style={{
                        background: sel ? "#0A1F44" : "#FFFFFF",
                        color: sel ? "#FFFFFF" : "#0A1F44",
                        border: sel
                          ? "1px solid #0A1F44"
                          : "1px solid #E2E8F0",
                        cursor: "pointer",
                      }}
                      data-testid={`standard-pick-${s.code}`}
                    >
                      {s.name_vi.split(" — ")[0]}
                      {s.is_default && " ★"}
                    </button>
                  );
                })}
              </div>
            ) : (
              standard && (
                <div className="text-xs" style={{ color: "#6B7280" }}>
                  Tiêu chuẩn: <strong>{standard.name_vi.split(" — ")[0]}</strong>
                  {" "}({standard.doc_types.length} mẫu tài liệu chuẩn)
                </div>
              )
            )}
          </div>
        )}

        {/* Step indicator */}
        <div
          className="grid items-center justify-center animate-section"
          style={{ gridTemplateColumns: "auto auto auto", gap: "8px" }}
        >
          {[
            { n: 1, label: "Chọn mẫu" },
            { n: 2, label: "Xác nhận & Tải về" },
          ].map((s, i) => (
            <div key={s.n} className="contents">
              <div
                className="grid items-center"
                style={{ gridTemplateColumns: "auto auto", gap: "8px" }}
              >
                <div
                  className="w-8 h-8 rounded-full grid place-items-center text-xs font-bold"
                  style={{
                    background: step >= s.n ? "#0A1F44" : "#E2E8F0",
                    color: step >= s.n ? "#fff" : "#6B7280",
                  }}
                >
                  {s.n}
                </div>
                <span
                  className="text-sm font-medium"
                  style={{ color: step >= s.n ? "#0A1F44" : "#6B7280" }}
                >
                  {s.label}
                </span>
              </div>
              {i < 1 && (
                <div
                  className="h-0.5 w-12"
                  style={{ background: step > s.n ? "#0A1F44" : "#E2E8F0" }}
                />
              )}
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <div
            className="px-4 py-3 rounded-xl text-sm"
            style={{
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.2)",
              color: "#f87171",
            }}
          >
            {error}
            <button onClick={() => setError("")} className="ml-2 font-bold">
              ×
            </button>
          </div>
        )}

        {/* ── STEP 1: Select templates ── */}
        {step === 1 && (
          <div className="space-y-6">
            {/* Company profile panel (read-only) */}
            <div
              className="rounded-2xl p-5"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div
                className="grid items-center mb-3"
                style={{ gridTemplateColumns: "1fr auto" }}
              >
                <h3
                  className="text-sm font-semibold"
                  style={{ color: "#0A1F44" }}
                >
                  Thông tin doanh nghiệp
                </h3>
                <Link
                  href="/settings/company"
                  className="text-xs px-3 py-1 rounded-lg transition-colors hover:opacity-80"
                  style={{
                    background: "rgba(10,31,68,0.1)",
                    color: "#0A1F44",
                    border: "1px solid rgba(10,31,68,0.2)",
                  }}
                >
                  Cập nhật
                </Link>
              </div>

              {!profileComplete && (
                <div
                  className="px-3 py-2 rounded-lg mb-3 text-xs"
                  style={{
                    background: "rgba(245,158,11,0.08)",
                    border: "1px solid rgba(245,158,11,0.2)",
                    color: "#f59e0b",
                  }}
                >
                  Thông tin chưa đầy đủ. Vui lòng vào{" "}
                  <Link href="/settings/company" className="underline font-semibold">
                    Thông tin doanh nghiệp
                  </Link>{" "}
                  để cập nhật trước khi tạo hồ sơ.
                </div>
              )}

              <div className="grid gap-2 grid-cols-1 sm:grid-cols-2">
                {profileRows.map((r) => (
                  <div key={r.label} className="text-xs">
                    <span style={{ color: "#6B7280" }}>{r.label}: </span>
                    {r.value ? (
                      <span
                        className="font-medium"
                        style={{ color: "#0A1F44" }}
                      >
                        {r.value}
                      </span>
                    ) : (
                      <span style={{ color: "#ef4444", fontStyle: "italic" }}>
                        Chưa cập nhật
                      </span>
                    )}
                  </div>
                ))}
                <div className="text-xs">
                  <span style={{ color: "#6B7280" }}>Ngày tạo: </span>
                  <span className="font-medium" style={{ color: "#0A1F44" }}>
                    {dateStr}
                  </span>
                </div>
              </div>
            </div>

            {/* Template list */}
            <div>
              <h2
                className="text-base font-bold mb-1"
                style={{ color: "#0A1F44" }}
              >
                Chọn mẫu tài liệu
              </h2>
              <p className="text-xs mb-4" style={{ color: "#6B7280" }}>
                Chọn tối đa 3 mẫu. Hệ thống sẽ thay thế các placeholder bằng
                thông tin doanh nghiệp.
              </p>

              {templates.length === 0 ? (
                <div
                  className="rounded-2xl p-8 text-center"
                  style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
                >
                  <p
                    className="text-sm font-semibold mb-1"
                    style={{ color: "#0A1F44" }}
                  >
                    Chưa có mẫu tài liệu
                  </p>
                  <p className="text-xs" style={{ color: "#6B7280" }}>
                    Admin cần upload template DOCX tại trang quản lý.
                  </p>
                </div>
              ) : (
                <div
                  className="grid gap-3"
                  style={{
                    gridTemplateColumns:
                      "repeat(auto-fill, minmax(180px, 1fr))",
                  }}
                >
                  {(standard
                    ? templates.filter((t) =>
                        standard.doc_types.some(
                          (dt) => dt.doc_type === t.doc_type,
                        ),
                      )
                    : templates
                  ).map((t) => {
                    const selected = selectedTypes.includes(t.doc_type);
                    const cov = coverageMap[t.doc_type];
                    // Coverage color: <40% red, 40-70% amber, ≥70% green
                    const covColor = cov
                      ? cov.coverage_pct >= 70
                        ? "#16A34A"
                        : cov.coverage_pct >= 40
                          ? "#D97706"
                          : "#DC2626"
                      : "#94A3B8";

                    return (
                      <button
                        key={t.doc_type}
                        onClick={() => toggleTemplate(t.doc_type)}
                        className="text-left rounded-xl p-4 transition-all"
                        style={{
                          background: selected
                            ? "rgba(10,31,68,0.06)"
                            : "#FFFFFF",
                          border: `2px solid ${selected ? "#0A1F44" : "#E2E8F0"}`,
                          cursor: "pointer",
                        }}
                        data-testid={`template-card-${t.doc_type}`}
                      >
                        <div
                          className="grid"
                          style={{
                            gridTemplateColumns: "auto 1fr",
                            gap: "12px",
                          }}
                        >
                          <div
                            className="w-5 h-5 rounded grid place-items-center mt-0.5"
                            style={{
                              border: `2px solid ${selected ? "#0A1F44" : "#E2E8F0"}`,
                              background: selected ? "#0A1F44" : "transparent",
                            }}
                          >
                            {selected && (
                              <svg
                                width="12"
                                height="12"
                                fill="none"
                                viewBox="0 0 24 24"
                                stroke="#fff"
                                strokeWidth={3}
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M5 13l4 4L19 7"
                                />
                              </svg>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div
                              className="text-sm font-semibold"
                              style={{ color: "#0A1F44" }}
                            >
                              {t.label}
                            </div>
                            <div
                              className="text-xs mt-1"
                              style={{ color: "#6B7280" }}
                            >
                              {[t.has_vi && "VI", t.has_en && "EN"]
                                .filter(Boolean)
                                .join(" · ")}
                            </div>
                            {cov && (
                              <div
                                className="text-[10px] mt-2 px-2 py-0.5 rounded inline-block font-mono"
                                style={{
                                  background: `${covColor}15`,
                                  color: covColor,
                                  border: `1px solid ${covColor}40`,
                                }}
                                title={`${cov.filled}/${cov.total} field đã fill`}
                              >
                                {cov.coverage_pct}% real data
                              </div>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Next button */}
            <div className="grid justify-end">
              <button
                onClick={() => setStep(2)}
                disabled={selectedTypes.length === 0 || !profileComplete}
                className="px-6 py-3 rounded-xl font-semibold text-sm transition-all"
                style={{
                  background:
                    selectedTypes.length > 0 && profileComplete
                      ? "#0A1F44"
                      : "#E2E8F0",
                  color:
                    selectedTypes.length > 0 && profileComplete
                      ? "#fff"
                      : "#6B7280",
                  cursor:
                    selectedTypes.length > 0 && profileComplete
                      ? "pointer"
                      : "not-allowed",
                }}
              >
                Tiếp theo
              </button>
            </div>
          </div>
        )}

        {/* ── STEP 2: Review & Generate ── */}
        {step === 2 && (
          <div className="space-y-6">
            {/* Language selection */}
            <div
              className="rounded-2xl p-5"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <h3
                className="text-xs font-medium mb-3"
                style={{ color: "#6B7280" }}
              >
                Ngôn ngữ tài liệu
              </h3>
              <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                {(
                  [
                    { id: "vi" as const, label: "Tiếng Việt", flag: "🇻🇳" },
                    { id: "en" as const, label: "English", flag: "🇬🇧" },
                  ] as const
                ).map((l) => {
                  const available = selectedTypes.every((dt) => {
                    const t = templates.find((tpl) => tpl.doc_type === dt);
                    return t && (l.id === "vi" ? t.has_vi : t.has_en);
                  });
                  return (
                    <button
                      key={l.id}
                      onClick={() => available && setLang(l.id)}
                      disabled={!available}
                      className="rounded-xl p-4 text-left transition-all"
                      style={{
                        background:
                          lang === l.id ? "rgba(10,31,68,0.06)" : "#FFFFFF",
                        border: `2px solid ${lang === l.id ? "#0A1F44" : "#E2E8F0"}`,
                        opacity: available ? 1 : 0.35,
                        cursor: available ? "pointer" : "not-allowed",
                      }}
                    >
                      <div className="text-lg mb-1">{l.flag}</div>
                      <div
                        className="text-sm font-semibold"
                        style={{ color: "#0A1F44" }}
                      >
                        {l.label}
                      </div>
                      {!available && (
                        <div
                          className="text-xs mt-1"
                          style={{ color: "#f59e0b" }}
                        >
                          Chưa có template
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Output format selection — show when ANY selected doc_type has its
                pdf_html_renderer_v1.* flag on. Per-doc fallback to DOCX is
                handled silently in handleGenerate. */}
            {selectedTypes.some((dt) => isPdfEnabledFor(dt)) && (
              <div
                className="rounded-2xl p-5"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                }}
              >
                <h3
                  className="text-xs font-medium mb-3"
                  style={{ color: "#6B7280" }}
                >
                  Định dạng tài liệu
                </h3>
                <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                  {(
                    [
                      {
                        id: "docx" as const,
                        label: "DOCX",
                        desc: "Mở bằng Word, có thể chỉnh sửa",
                      },
                      {
                        id: "pdf" as const,
                        label: "PDF (đẹp)",
                        desc: "Layout chuyên nghiệp, font Inter, sẵn sàng in",
                      },
                    ] as const
                  ).map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => setOutputFormat(opt.id)}
                      className="rounded-xl p-4 text-left transition-all"
                      style={{
                        background:
                          outputFormat === opt.id
                            ? "rgba(10,31,68,0.06)"
                            : "#FFFFFF",
                        border: `2px solid ${outputFormat === opt.id ? "#0A1F44" : "#E2E8F0"}`,
                        cursor: "pointer",
                      }}
                    >
                      <div
                        className="text-sm font-semibold"
                        style={{ color: "#0A1F44" }}
                      >
                        {opt.label}
                      </div>
                      <div
                        className="text-xs mt-1"
                        style={{ color: "#6B7280" }}
                      >
                        {opt.desc}
                      </div>
                    </button>
                  ))}
                </div>
                {outputFormat === "pdf" &&
                  selectedTypes.some((dt) => !isPdfEnabledFor(dt)) && (
                    <div
                      className="text-xs mt-3"
                      style={{ color: "#d97706" }}
                    >
                      Lưu ý: PDF chuyên nghiệp đang hỗ trợ:{" "}
                      <strong>
                        {selectedTypes
                          .filter(isPdfEnabledFor)
                          .map(
                            (dt) =>
                              templates.find((t) => t.doc_type === dt)?.label ||
                              dt,
                          )
                          .join(", ")}
                      </strong>
                      . Các tài liệu còn lại sẽ tự động tạo bản DOCX.
                    </div>
                  )}
              </div>
            )}

            {/* Summary */}
            <div
              className="rounded-2xl p-5"
              style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
            >
              <div className="mb-4">
                <h3
                  className="text-xs font-medium mb-2"
                  style={{ color: "#6B7280" }}
                >
                  Tài liệu sẽ tạo
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedTypes.map((dt) => {
                    const t = templates.find((tpl) => tpl.doc_type === dt);
                    return (
                      <span
                        key={dt}
                        className="px-3 py-1 rounded-full text-xs font-medium"
                        style={{
                          background: "rgba(10,31,68,0.1)",
                          color: "#0A1F44",
                        }}
                      >
                        {t?.label || dt}
                      </span>
                    );
                  })}
                </div>
              </div>

              <div
                style={{ borderTop: "1px solid #E2E8F0", paddingTop: "16px" }}
              >
                <h3
                  className="text-xs font-medium mb-2"
                  style={{ color: "#6B7280" }}
                >
                  Thông tin sẽ điền vào template
                </h3>
                <div className="grid gap-2 grid-cols-1 sm:grid-cols-2">
                  {[
                    ...profileRows,
                    { label: "Ngày tạo", value: dateStr, key: "ngay_tao" },
                  ]
                    .filter((r) => r.value)
                    .map((r) => (
                      <div key={r.label} className="text-xs">
                        <span style={{ color: "#6B7280" }}>{r.label}: </span>
                        <span
                          className="font-medium"
                          style={{ color: "#0A1F44" }}
                        >
                          {r.value}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            {/* Success */}
            {generated && (
              <div
                className="px-4 py-3 rounded-xl text-sm"
                style={{
                  background: "rgba(10,31,68,0.08)",
                  border: "1px solid rgba(10,31,68,0.2)",
                  color: "#0A1F44",
                }}
              >
                Tạo thành công {selectedTypes.length} file{" "}
                {outputFormat === "pdf" ? "PDF" : "DOCX"}! Kiểm tra thư
                mục Downloads.
              </div>
            )}

            {/* Actions */}
            <div
              className="grid items-center"
              style={{ gridTemplateColumns: "auto 1fr", gap: "12px" }}
            >
              <button
                onClick={() => {
                  setStep(1);
                  setGenerated(false);
                }}
                className="px-5 py-3 rounded-xl text-sm"
                style={{ color: "#6B7280" }}
              >
                Quay lại
              </button>

              <button
                onClick={handleGenerate}
                disabled={generating}
                className="w-full py-3.5 rounded-xl font-semibold text-base transition-all duration-200 ease-out hover:scale-[1.01] active:scale-[0.99]"
                style={{
                  background: generating ? "#E2E8F0" : "#0A1F44",
                  color: "#fff",
                  cursor: generating ? "not-allowed" : "pointer",
                  boxShadow: generating
                    ? "none"
                    : "0 4px 20px rgba(10,31,68,0.35)",
                }}
              >
                {generating ? (
                  <span className="grid grid-flow-col items-center gap-2 justify-center">
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    Đang tạo...
                  </span>
                ) : (
                  `Tạo ${selectedTypes.length} file ${outputFormat === "pdf" ? "PDF" : "DOCX"}`
                )}
              </button>
            </div>

            {/* Info */}
            <div
              className="rounded-xl p-4 text-xs"
              style={{
                background: "#F5F1E8",
                border: "1px solid #E2E8F0",
                color: "#6B7280",
              }}
            >
              <strong style={{ color: "#374151" }}>Cách hoạt động:</strong>
              <ul className="mt-2 space-y-1 list-disc pl-4">
                <li>Hệ thống lấy file DOCX mẫu do admin upload sẵn</li>
                <li>
                  Tự động thay thế {`{{ten_cong_ty}}`}, {`{{ten_giam_doc}}`},{" "}
                  {`{{dia_chi}}`},... bằng thông tin doanh nghiệp
                </li>
                <li>
                  File tải về giữ nguyên thiết kế, font, bảng biểu của template
                  gốc
                </li>
                <li>
                  Mở bằng Word/LibreOffice để chỉnh sửa thêm, sau đó upload lại
                  để đánh giá
                </li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
