"use client";

import { useState } from "react";
import Link from "next/link";
import { useUserAuth } from "@/components/UserAuthContext";

export default function DataExportPage() {
  const { token } = useUserAuth();
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  const [lastFilename, setLastFilename] = useState<string | null>(null);

  const onExport = async () => {
    setError("");
    setLastFilename(null);
    setDownloading(true);
    try {
      if (!token) throw new Error("Bạn cần đăng nhập để xuất dữ liệu");

      const res = await fetch("/api/api/users/me/export-data", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Lỗi ${res.status}`);
      }

      // Pull filename from Content-Disposition; fall back to a generated name
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="([^"]+)"/);
      const filename = match?.[1] ?? `aminra-export-${Date.now()}.json`;

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);

      setLastFilename(filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi không xác định");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <article className="max-w-3xl mx-auto px-6 py-10" data-page>
      <Link href="/settings" className="text-sm" style={{ color: "#0A1F44" }}>
        ← Quay lại Cài đặt
      </Link>

      <h1 className="text-3xl font-bold mt-4 mb-3" style={{ color: "#0A1F44" }}>
        Xuất dữ liệu cá nhân
      </h1>

      <p className="text-sm mb-6" style={{ color: "#6B7280" }}>
        Theo Nghị định 13/2023/NĐ-CP (Việt Nam) và GDPR Article 20 (EU), bạn có
        quyền yêu cầu một bản sao toàn bộ dữ liệu cá nhân chúng tôi đang lưu trữ
        về bạn ở định dạng máy đọc được (JSON).
      </p>

      <section
        className="bg-white rounded-2xl p-6 mb-6"
        style={{ border: "1px solid #E2E8F0" }}
      >
        <h2 className="text-base font-bold mb-3" style={{ color: "#0A1F44" }}>
          Bản xuất sẽ bao gồm:
        </h2>
        <ul className="text-sm space-y-1.5" style={{ color: "#374151" }}>
          <li>✓ Thông tin tài khoản (email, doanh nghiệp, vai trò)</li>
          <li>✓ Toàn bộ thông báo (notifications) đã nhận</li>
          <li>✓ Lịch sử hoạt động (audit log) liên quan tới tài khoản</li>
          <li>✓ Hồ sơ chứng nhận (submissions) đã gửi/nhận</li>
          <li>✓ Tài liệu, chứng chỉ, audit visit</li>
          <li>✓ Supply chain: nhà cung cấp, nguyên liệu, lô sản xuất</li>
        </ul>
        <p className="text-xs mt-4" style={{ color: "#94A3B8" }}>
          Mật khẩu (đã hash) và secrets không được bao gồm. Audit log có thể
          được giữ vượt quá thời điểm xoá tài khoản theo nghĩa vụ pháp lý (tối
          thiểu 5 năm).
        </p>
      </section>

      <button
        onClick={onExport}
        disabled={downloading}
        className="px-6 py-3 rounded-xl font-semibold text-sm transition-all"
        style={{
          background: downloading ? "#94A3B8" : "#0A1F44",
          color: "white",
          cursor: downloading ? "not-allowed" : "pointer",
        }}
      >
        {downloading ? "Đang chuẩn bị file..." : "Tải bản xuất dữ liệu (JSON)"}
      </button>

      {error && (
        <div
          role="alert"
          className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3 text-sm"
          style={{ color: "#991b1b" }}
        >
          {error}
        </div>
      )}

      {lastFilename && (
        <div
          role="status"
          className="mt-4 bg-[#DCE3F0] border border-[#DCE3F0] rounded-lg p-3 text-sm"
          style={{ color: "#0A1F44" }}
        >
          ✓ Đã tải <code>{lastFilename}</code>
        </div>
      )}

      <p className="text-xs mt-6" style={{ color: "#94A3B8" }}>
        Yêu cầu giới hạn 3 lần / giờ. Mỗi lần xuất được ghi lại trong audit log
        để bảo mật.
      </p>

      <DeletionRequestSection />
    </article>
  );
}

function DeletionRequestSection() {
  const { token } = useUserAuth();
  const [requesting, setRequesting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [error, setError] = useState("");

  const onRequestDeletion = async () => {
    if (
      !confirm(
        "Bạn chắc chắn muốn xoá tài khoản? Chúng tôi sẽ gửi email xác nhận. " +
          "Sau khi xác nhận, tài khoản sẽ bị xoá vĩnh viễn và không thể khôi phục.",
      )
    )
      return;

    setRequesting(true);
    setError("");
    try {
      if (!token) throw new Error("Bạn cần đăng nhập");

      const res = await fetch("/api/api/users/me/request-deletion", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ lang: "vi" }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);
      setRequested(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi");
    } finally {
      setRequesting(false);
    }
  };

  return (
    <section className="mt-12 pt-8 border-t" style={{ borderColor: "#E2E8F0" }}>
      <h2 className="text-base font-bold mb-2" style={{ color: "#7f1d1d" }}>
        Xoá tài khoản (Quyền được lãng quên)
      </h2>
      <p className="text-xs mb-4" style={{ color: "#6B7280" }}>
        Theo Nghị định 13 / GDPR Article 17, bạn có quyền yêu cầu xoá tài khoản.
        Chúng tôi sẽ gửi email xác nhận trước khi thực hiện. Hành động này không
        thể khôi phục.
      </p>

      {requested ? (
        <div
          role="status"
          className="bg-[#DCE3F0] border border-[#DCE3F0] rounded-lg p-3 text-sm"
          style={{ color: "#0A1F44" }}
        >
          ✓ Email xác nhận đã gửi tới hộp thư của bạn. Vui lòng nhấn link xác
          nhận trong vòng 60 phút.
        </div>
      ) : (
        <button
          onClick={onRequestDeletion}
          disabled={requesting}
          className="px-5 py-2.5 rounded-lg font-medium text-sm"
          style={{
            background: "transparent",
            border: "1px solid #dc2626",
            color: "#dc2626",
            cursor: requesting ? "not-allowed" : "pointer",
          }}
        >
          {requesting ? "Đang gửi..." : "Yêu cầu xoá tài khoản"}
        </button>
      )}

      {error && (
        <p role="alert" className="mt-3 text-xs" style={{ color: "#991b1b" }}>
          {error}
        </p>
      )}
    </section>
  );
}
