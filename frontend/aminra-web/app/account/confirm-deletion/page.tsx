"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { purgeAuthSessionState } from "@/lib/auth-session-cleanup";

function ConfirmDeletionContent() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";

  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const onConfirm = async () => {
    if (!token) {
      setError("Liên kết không hợp lệ — thiếu token");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch("/api/api/users/me/confirm-deletion", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Lỗi ${res.status}`);

      await purgeAuthSessionState("self_reset");

      setDone(true);
      setTimeout(() => router.push("/"), 5000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lỗi không xác định");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <article className="max-w-xl mx-auto px-6 py-12" data-page>
      <h1 className="text-3xl font-bold mb-3" style={{ color: "#0A1F44" }}>
        Xác nhận xoá tài khoản
      </h1>

      {done ? (
        <div
          role="status"
          className="bg-[#DCE3F0] border border-[#DCE3F0] rounded-2xl p-6 text-sm"
          style={{ color: "#0A1F44" }}
        >
          <p className="font-semibold mb-2">✓ Tài khoản đã được xoá</p>
          <p>
            Email và thông tin liên hệ đã được ẩn danh. Audit log có thể được
            giữ tới 5 năm theo nghĩa vụ pháp lý. Đang chuyển về trang chủ trong
            5 giây...
          </p>
          <Link
            href="/"
            className="inline-block mt-4 font-medium"
            style={{ color: "#0A1F44" }}
          >
            Về trang chủ ngay →
          </Link>
        </div>
      ) : (
        <>
          <div
            className="bg-red-50 border border-red-200 rounded-2xl p-5 mb-6 text-sm"
            style={{ color: "#7f1d1d" }}
          >
            <p className="font-semibold mb-2">
              Bạn đang xác nhận xoá tài khoản AMINRA của mình.
            </p>
            <p>
              Hành động này <strong>không thể khôi phục</strong>. Khi xác nhận:
            </p>
            <ul className="mt-2 ml-4 list-disc space-y-1">
              <li>Tài khoản bị vô hiệu hoá vĩnh viễn</li>
              <li>Email + tên doanh nghiệp + thông tin liên hệ được ẩn danh</li>
              <li>Audit log có thể được giữ tới 5 năm</li>
              <li>Chứng chỉ Halal đã cấp vẫn còn trên public verify</li>
            </ul>
          </div>

          <div className="flex gap-3">
            <button
              onClick={onConfirm}
              disabled={submitting || !token}
              className="px-6 py-3 rounded-xl font-semibold text-sm"
              style={{
                background: submitting || !token ? "#94A3B8" : "#dc2626",
                color: "white",
                cursor: submitting || !token ? "not-allowed" : "pointer",
              }}
            >
              {submitting ? "Đang xoá..." : "Tôi xác nhận xoá tài khoản"}
            </button>
            <Link
              href="/settings"
              className="px-6 py-3 rounded-xl font-semibold text-sm"
              style={{ background: "#F1F5F9", color: "#0A1F44" }}
            >
              Huỷ
            </Link>
          </div>

          {error && (
            <div
              role="alert"
              className="mt-4 bg-red-100 border border-red-300 rounded-lg p-3 text-sm"
              style={{ color: "#991b1b" }}
            >
              {error}
            </div>
          )}
        </>
      )}
    </article>
  );
}

export default function ConfirmDeletionPage() {
  return (
    <Suspense
      fallback={
        <article className="max-w-xl mx-auto px-6 py-12" data-page>
          <p className="text-sm" style={{ color: "#6B7280" }}>
            Đang tải liên kết xác nhận...
          </p>
        </article>
      }
    >
      <ConfirmDeletionContent />
    </Suspense>
  );
}
