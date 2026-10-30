"use client";

import { useState, useEffect, useRef, use } from "react";

interface PortalInfo {
  supplier_name: string;
  business_name: string;
  required_documents: { type: string; label: string; required: boolean }[];
  uploaded_certificates: {
    id: string;
    cert_type: string;
    filename: string;
    size: number;
    uploaded_at: string;
  }[];
}

export default function SupplierPortalPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = use(params);
  const [info, setInfo] = useState<PortalInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState("halal_cert");
  const [success, setSuccess] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchInfo = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/api/supply-chain/supplier-portal/${token}`);
      if (res.status === 410) {
        setError(
          "Link đã hết hạn. Vui lòng liên hệ doanh nghiệp để nhận link mới.",
        );
        return;
      }
      if (!res.ok) {
        setError("Link không hợp lệ.");
        return;
      }
      setInfo(await res.json());
    } catch {
      setError("Không thể tải thông tin.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInfo();
  }, [token]);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setSuccess("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("cert_type", uploadType);
      const res = await fetch(
        `/api/api/supply-chain/supplier-portal/${token}/upload`,
        { method: "POST", body: fd },
      );
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        alert(e.detail || "Upload thất bại");
        return;
      }
      setSuccess(`Đã gửi "${file.name}" thành công!`);
      fetchInfo();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  if (loading)
    return (
      <div
        className="min-h-screen grid place-items-center"
        style={{ background: "#F5F1E8" }}
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

  if (error)
    return (
      <div
        className="min-h-screen grid place-items-center p-6"
        style={{ background: "#F5F1E8" }}
      >
        <div className="max-w-md text-center">
          <div
            className="w-16 h-16 rounded-full grid place-items-center mx-auto mb-4"
            style={{ background: "#FEF2F2" }}
          >
            <svg
              className="w-8 h-8"
              style={{ color: "#DC2626" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
              />
            </svg>
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ color: "#0A1F44" }}>
            Không thể truy cập
          </h1>
          <p className="text-sm" style={{ color: "#6B7280" }}>
            {error}
          </p>
        </div>
      </div>
    );

  if (!info) return null;

  const uploadedTypes = new Set(
    info.uploaded_certificates.map((c) => c.cert_type),
  );

  return (
    <div className="min-h-screen" style={{ background: "#F5F1E8" }} data-page>
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div className="text-center animate-section">
          <div
            className="w-14 h-14 rounded-2xl grid place-items-center mx-auto mb-4"
            style={{ background: "#0A1F44" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-9 h-9" />
          </div>
          <h1 className="text-2xl font-bold" style={{ color: "#0A1F44" }}>
            Gửi hồ sơ nhà cung cấp
          </h1>
          <p className="text-sm mt-2" style={{ color: "#6B7280" }}>
            <strong style={{ color: "#374151" }}>{info.business_name}</strong>{" "}
            yêu cầu{" "}
            <strong style={{ color: "#374151" }}>{info.supplier_name}</strong>{" "}
            gửi hồ sơ chứng nhận
          </p>
        </div>

        {/* Required documents checklist */}
        <div
          className="rounded-2xl p-6 animate-section"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          <h2 className="text-sm font-bold mb-4" style={{ color: "#0A1F44" }}>
            Hồ sơ yêu cầu
          </h2>
          <div className="space-y-2">
            {info.required_documents.map((doc) => {
              const done = uploadedTypes.has(doc.type);
              return (
                <div
                  key={doc.type}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
                  style={{
                    background: done ? "#DCE3F0" : "#FFFFFF",
                    border: `1px solid ${done ? "#D9B96E" : "#E2E8F0"}`,
                  }}
                >
                  <div
                    className="w-5 h-5 rounded grid place-items-center flex-shrink-0"
                    style={{
                      background: done ? "#102A5C" : "#E2E8F0",
                      border: `2px solid ${done ? "#102A5C" : "#D1D5DB"}`,
                    }}
                  >
                    {done && (
                      <svg
                        width="10"
                        height="10"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="#fff"
                        strokeWidth={4}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                  </div>
                  <span
                    className="text-sm flex-1"
                    style={{ color: done ? "#102A5C" : "#374151" }}
                  >
                    {doc.label}
                  </span>
                  {doc.required && !done && (
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: "#FEF2F2", color: "#DC2626" }}
                    >
                      Bắt buộc
                    </span>
                  )}
                  {done && (
                    <span className="text-xs" style={{ color: "#102A5C" }}>
                      Đã gửi
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Upload section */}
        <div
          className="rounded-2xl p-6 animate-section"
          style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
        >
          <h2 className="text-sm font-bold mb-4" style={{ color: "#0A1F44" }}>
            Gửi hồ sơ
          </h2>
          <div className="space-y-3">
            <div>
              <label
                className="block text-xs font-medium mb-1"
                style={{ color: "#6B7280" }}
              >
                Loại hồ sơ
              </label>
              <select
                value={uploadType}
                onChange={(e) => setUploadType(e.target.value)}
                className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                style={{
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                  color: "#374151",
                }}
              >
                {info.required_documents.map((d) => (
                  <option key={d.type} value={d.type}>
                    {d.label}
                    {d.required ? " (bắt buộc)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <input
              ref={fileRef}
              type="file"
              className="hidden"
              accept=".pdf,.docx,.jpg,.jpeg,.png"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full py-3 rounded-xl text-sm font-semibold text-white transition-all"
              style={{
                background: uploading ? "#E2E8F0" : "#0A1F44",
                color: uploading ? "#9CA3AF" : "#fff",
              }}
            >
              {uploading ? "Đang gửi..." : "Chọn file và gửi"}
            </button>
            <p className="text-xs text-center" style={{ color: "#9CA3AF" }}>
              PDF, DOCX, JPG, PNG · Tối đa 10MB
            </p>
          </div>
          {success && (
            <div
              className="mt-3 px-3 py-2 rounded-lg text-xs animate-toast"
              style={{
                background: "#DCE3F0",
                border: "1px solid #D9B96E",
                color: "#102A5C",
              }}
            >
              {success}
            </div>
          )}
        </div>

        {/* Uploaded files */}
        {info.uploaded_certificates.length > 0 && (
          <div
            className="rounded-2xl p-6 animate-section"
            style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
          >
            <h2 className="text-sm font-bold mb-3" style={{ color: "#0A1F44" }}>
              Hồ sơ đã gửi ({info.uploaded_certificates.length})
            </h2>
            <div className="space-y-2">
              {info.uploaded_certificates.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-3 px-3 py-2.5 rounded-lg"
                  style={{ background: "#FFFFFF", border: "1px solid #E2E8F0" }}
                >
                  <div
                    className="w-8 h-8 rounded-lg grid place-items-center"
                    style={{ background: "#DCE3F0" }}
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
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p
                      className="text-sm font-medium truncate"
                      style={{ color: "#374151" }}
                    >
                      {c.filename}
                    </p>
                    <p className="text-xs" style={{ color: "#9CA3AF" }}>
                      {(c.size / 1024).toFixed(0)} KB ·{" "}
                      {new Date(c.uploaded_at).toLocaleDateString("vi-VN")}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <p className="text-xs text-center" style={{ color: "#9CA3AF" }}>
          Hồ sơ được gửi trực tiếp đến {info.business_name} qua nền tảng AMINRA
        </p>
      </div>
    </div>
  );
}
