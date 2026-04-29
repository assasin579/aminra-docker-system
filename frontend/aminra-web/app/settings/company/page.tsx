"use client";

import { useState, useEffect } from "react";
import { useUserAuth } from "@/components/UserAuthContext";
import Link from "next/link";

export default function CompanySettingsPage() {
  const { user, token, isAuthenticated } = useUserAuth();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    company_name: "",
    representative_name: "",
    address: "",
    phone: "",
    email: "",
    manager_name: "",
  });

  const headers = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    setLoading(true);
    fetch("/api/auth/company-profile", { headers })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data)
          setForm({
            company_name: data.company_name || "",
            representative_name: data.representative_name || "",
            address: data.address || "",
            phone: data.phone || "",
            email: data.email || "",
            manager_name: data.manager_name || "",
          });
      })
      .catch(() => setError("Không thể tải thông tin"))
      .finally(() => setLoading(false));
  }, [isAuthenticated, token]);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const res = await fetch("/api/auth/company-profile", {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: form.company_name || null,
          representative_name: form.representative_name || null,
          address: form.address || null,
          phone: form.phone || null,
          email: form.email || null,
          manager_name: form.manager_name || null,
        }),
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

  const updateField = (key: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen grid place-items-center">
        <div className="text-center space-y-4">
          <p style={{ color: "#6B7280" }}>Vui lòng đăng nhập</p>
          <Link
            href="/business/login"
            className="inline-block px-6 py-3 rounded-xl font-semibold text-white"
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

  const isOwner = user?.is_owner;
  const cardStyle = { background: "#FFFFFF", border: "1px solid #E2E8F0" };
  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };

  const fields: {
    key: keyof typeof form;
    label: string;
    placeholder: string;
    type?: string;
  }[] = [
    {
      key: "company_name",
      label: "Tên công ty",
      placeholder: "VD: Công ty TNHH Thực phẩm ABC",
    },
    {
      key: "representative_name",
      label: "Giám đốc / Người đại diện",
      placeholder: "VD: Nguyễn Văn A",
    },
    {
      key: "address",
      label: "Địa chỉ",
      placeholder: "VD: 123 Nguyễn Huệ, Q.1, TP.HCM",
    },
    {
      key: "phone",
      label: "Số điện thoại",
      placeholder: "VD: 028-1234-5678",
      type: "tel",
    },
    {
      key: "email",
      label: "Email công ty",
      placeholder: "VD: info@abc.com.vn",
      type: "email",
    },
    {
      key: "manager_name",
      label: "Người quản lý hệ thống (Admin DN)",
      placeholder: "VD: Trần Văn B",
    },
  ];

  return (
    <div style={{ background: "#FFFFFF" }} data-page>
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
        <div className="animate-section">
          <h1 className="text-xl font-bold" style={{ color: "#0A1F44" }}>
            Thông tin doanh nghiệp
          </h1>
          <p className="text-sm mt-1" style={{ color: "#6B7280" }}>
            Thông tin này được sử dụng khi tạo hồ sơ và đăng ký chứng nhận Halal
          </p>
        </div>

        <div
          className="rounded-2xl p-6 space-y-5 animate-section"
          style={cardStyle}
        >
          {!isOwner && (
            <div
              className="px-4 py-3 rounded-lg text-xs leading-relaxed"
              style={{
                background: "#FFFBEB",
                border: "1px solid #FDE68A",
                color: "#B45309",
              }}
            >
              <strong>Tài khoản thành viên.</strong> Thông tin công ty được quản
              lý bởi chủ tài khoản đã mời bạn.
            </div>
          )}

          {fields.map((f) => (
            <div key={f.key}>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6B7280" }}
              >
                {f.label}
              </label>
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
              />
            </div>
          ))}

          {error && (
            <div
              className="px-3 py-2 rounded-lg text-xs animate-toast"
              style={{
                background: "#FEF2F2",
                border: "1px solid #FECACA",
                color: "#DC2626",
              }}
            >
              {error}
            </div>
          )}
          {saved && (
            <div
              className="px-3 py-2 rounded-lg text-xs animate-toast"
              style={{
                background: "#DCE3F0",
                border: "1px solid #D9B96E",
                color: "#102A5C",
              }}
            >
              Đã lưu thành công
            </div>
          )}

          {isOwner && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="w-full py-2.5 rounded-xl font-semibold text-sm transition-all text-white"
              style={{
                background: saving ? "#E2E8F0" : "#0A1F44",
                color: saving ? "#9CA3AF" : "#fff",
              }}
            >
              {saving ? "Đang lưu..." : "Lưu thông tin"}
            </button>
          )}
        </div>

        <div className="pb-6" />
      </div>
    </div>
  );
}
