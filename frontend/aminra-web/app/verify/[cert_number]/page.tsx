"use client";

import { useState, useEffect, use } from "react";

interface BlockchainProof {
  anchored: boolean;
  chain?: "polygon" | "bitcoin";
  merkle_root?: string;
  tx_hash?: string;
  block_number?: number;
  anchored_at?: string;
  explorer_url?: string;
  leaf_hash?: string;
  merkle_proof?: { sibling: string; position: "left" | "right" }[];
  verify_instructions?: string;
  note?: string;
}

interface VerifyData {
  cert_number: string;
  company_name: string;
  provider_name: string;
  issue_date: string;
  expiry_date: string;
  status: string;
  valid: boolean;
  blockchain?: BlockchainProof;
  revocation?: {
    reason: string;
    revoked_at: string | null;
  } | null;
}

function formatDate(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function invalidMessage(data: VerifyData): string {
  if (data.status === "expired") return "Chứng nhận đã hết hạn";
  if (data.status === "suspended") return "Chứng nhận đã bị đình chỉ";
  if (data.status === "revoked") return "Chứng nhận đã bị thu hồi";
  return "Chứng nhận không hợp lệ";
}

export default function VerifyPage({
  params,
}: {
  params: Promise<{ cert_number: string }>;
}) {
  const { cert_number } = use(params);
  return <VerifyContent cert_number={cert_number} />;
}

export function VerifyContent({ cert_number }: { cert_number: string }) {
  const [data, setData] = useState<VerifyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!cert_number) return;
    setLoading(true);
    fetch(
      `/api/api/submissions/certificates/public/${encodeURIComponent(cert_number)}`,
    )
      .then((r) => {
        if (r.status === 404) throw new Error("not_found");
        if (!r.ok) throw new Error("error");
        return r.json();
      })
      .then((d) => setData(d))
      .catch((e) => setError(e.message === "not_found" ? "not_found" : "error"))
      .finally(() => setLoading(false));
  }, [cert_number]);

  // Loading
  if (loading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "#F5F1E8" }}
      >
        <div className="text-center animate-scale-in">
          <div
            className="w-16 h-16 mx-auto mb-4 rounded-2xl grid place-items-center"
            style={{ background: "#0A1F44" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/aminra-mark.png" alt="AMINRA" className="w-10 h-10" />
          </div>
          <div className="flex items-center justify-center gap-2 mt-4">
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
            <div className="w-2 h-2 rounded-full bg-[#0A1F44] animate-pulse-dot" />
          </div>
          <p className="text-sm mt-3" style={{ color: "#6B7280" }}>
            Đang xác minh chứng nhận...
          </p>
        </div>
      </div>
    );
  }

  // Error — not found
  if (error || !data) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "#F5F1E8" }}
      >
        <div className="text-center animate-scale-in max-w-md px-6">
          <div
            className="w-20 h-20 mx-auto mb-5 rounded-full grid place-items-center animate-empty-icon"
            style={{
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            <svg
              className="w-10 h-10"
              style={{ color: "#EF4444" }}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
          </div>
          <h1 className="text-xl font-bold mb-2" style={{ color: "#0A1F44" }}>
            Không tìm thấy chứng nhận
          </h1>
          <p className="text-sm" style={{ color: "#6B7280" }}>
            Mã chứng nhận không tồn tại hoặc không hợp lệ. Vui lòng kiểm tra
            lại.
          </p>
          <div className="mt-6 pt-4" style={{ borderTop: "1px solid #E2E8F0" }}>
            <p className="text-xs" style={{ color: "#94A3B8" }}>
              Powered by AMINRA
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "#F5F1E8" }} data-page>
      {/* Hero header — green gradient */}
      <div
        style={{
          background:
            "linear-gradient(135deg, #0A1F44 0%, #0A1F44 50%, #0A9B6C 100%)",
        }}
      >
        <div className="max-w-md mx-auto px-5 py-8 md:py-12">
          <div className="flex items-center gap-3 mb-6 animate-section">
            <div
              className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
              style={{
                background: "rgba(255,255,255,0.15)",
                backdropFilter: "blur(8px)",
              }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/aminra-mark.png" alt="AMINRA" className="w-7 h-7" />
            </div>
            <div>
              <p className="text-white/60 text-xs font-medium tracking-wider uppercase">
                AMINRA Xác minh chứng nhận
              </p>
            </div>
          </div>

          <div className="animate-section">
            <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">
              Xác minh chứng nhận Halal
            </h1>
            <span
              className="px-3 py-1.5 rounded-lg text-xs font-bold tracking-wide"
              style={{
                background: "rgba(255,255,255,0.15)",
                color: "white",
                backdropFilter: "blur(4px)",
              }}
            >
              #{data.cert_number}
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-md mx-auto px-5 -mt-4 pb-12 space-y-4">
        {/* Validity card */}
        <div
          className="rounded-2xl p-6 text-center animate-section"
          style={{
            background: data.valid
              ? "linear-gradient(135deg, #DCE3F0, #D9B96E)"
              : "linear-gradient(135deg, #FEF2F2, #FECACA)",
            border: `1px solid ${data.valid ? "rgba(10,31,68,0.2)" : "rgba(220,38,38,0.2)"}`,
            boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
          }}
        >
          {data.valid ? (
            <>
              <div
                className="w-16 h-16 mx-auto mb-4 rounded-full grid place-items-center"
                style={{ background: "rgba(10,31,68,0.15)" }}
              >
                <svg
                  className="w-8 h-8"
                  style={{ color: "#0A1F44" }}
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
              </div>
              <h2
                className="text-xl font-bold mb-1"
                style={{ color: "#0A1F44" }}
              >
                Chứng nhận hợp lệ
              </h2>
              <p className="text-sm" style={{ color: "#047857" }}>
                Chứng nhận Halal này đang có hiệu lực
              </p>
            </>
          ) : (
            <>
              <div
                className="w-16 h-16 mx-auto mb-4 rounded-full grid place-items-center"
                style={{ background: "rgba(220,38,38,0.15)" }}
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </div>
              <h2
                className="text-xl font-bold mb-1"
                style={{ color: "#991B1B" }}
              >
                {invalidMessage(data)}
              </h2>
              <p className="text-sm" style={{ color: "#DC2626" }}>
                Chứng nhận này không còn hiệu lực
              </p>
              {data.status === "revoked" && data.revocation?.reason && (
                <div
                  className="mt-4 px-4 py-3 rounded-lg text-left text-sm"
                  style={{
                    background: "rgba(220,38,38,0.08)",
                    border: "1px solid rgba(220,38,38,0.2)",
                  }}
                  data-revocation
                >
                  <p
                    className="font-semibold mb-1"
                    style={{ color: "#7f1d1d" }}
                  >
                    Lý do thu hồi:
                  </p>
                  <p style={{ color: "#7f1d1d" }}>{data.revocation.reason}</p>
                  {data.revocation.revoked_at && (
                    <p className="text-xs mt-2" style={{ color: "#991b1b" }}>
                      Thu hồi ngày {formatDate(data.revocation.revoked_at)}
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Details card */}
        <div
          className="rounded-2xl overflow-hidden animate-section"
          style={{
            background: "#FFFFFF",
            border: "1px solid #E2E8F0",
            boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
          }}
        >
          <div
            className="px-5 py-4"
            style={{ borderBottom: "1px solid #E2E8F0" }}
          >
            <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
              Thông tin chứng nhận
            </h3>
          </div>
          <div className="divide-y" style={{ borderColor: "#F0F0F0" }}>
            {[
              { label: "Mã chứng nhận", value: data.cert_number },
              { label: "Doanh nghiệp", value: data.company_name },
              { label: "Tổ chức cấp", value: data.provider_name },
              { label: "Ngày cấp", value: formatDate(data.issue_date) },
              { label: "Ngày hết hạn", value: formatDate(data.expiry_date) },
            ].map((row, i) => (
              <div
                key={i}
                className={`px-5 py-3 flex items-center justify-between animate-list-item stagger-${Math.min(i + 1, 12)}`}
              >
                <span className="text-xs" style={{ color: "#6B7280" }}>
                  {row.label}
                </span>
                <span
                  className="text-sm font-medium"
                  style={{ color: "#0A1F44" }}
                >
                  {row.value}
                </span>
              </div>
            ))}
            <div
              className={`px-5 py-3 flex items-center justify-between animate-list-item stagger-6`}
            >
              <span className="text-xs" style={{ color: "#6B7280" }}>
                Trạng thái
              </span>
              <span
                className="px-2.5 py-0.5 rounded-full text-xs font-semibold"
                style={{
                  background:
                    data.status === "active"
                      ? "rgba(10,31,68,0.12)"
                      : data.status === "suspended"
                        ? "rgba(217,119,6,0.12)"
                        : data.status === "revoked"
                          ? "rgba(220,38,38,0.12)"
                          : "rgba(107,114,128,0.12)",
                  color:
                    data.status === "active"
                      ? "#0A1F44"
                      : data.status === "suspended"
                        ? "#D97706"
                        : data.status === "revoked"
                          ? "#DC2626"
                          : "#6B7280",
                }}
              >
                {data.status === "active"
                  ? "Hoạt động"
                  : data.status === "suspended"
                    ? "Đình chỉ"
                    : data.status === "revoked"
                      ? "Thu hồi"
                      : "Hết hạn"}
              </span>
            </div>
          </div>
        </div>

        {/* Blockchain anchor card */}
        {data.blockchain && (
          <div
            className="rounded-2xl overflow-hidden animate-section"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 4px 20px rgba(0,0,0,0.04)",
            }}
          >
            <div
              className="px-5 py-4"
              style={{ borderBottom: "1px solid #E2E8F0" }}
            >
              <div className="flex items-center gap-2">
                <svg
                  className="w-4 h-4"
                  style={{ color: "#7c3aed" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
                <h3 className="text-sm font-bold" style={{ color: "#0A1F44" }}>
                  Blockchain verification
                </h3>
              </div>
            </div>
            {data.blockchain.anchored ? (
              <div className="px-5 py-4 space-y-2">
                <div className="flex items-center gap-2">
                  <span
                    className="px-2 py-0.5 rounded-full text-xs font-semibold"
                    style={{
                      background: "rgba(124, 58, 237, 0.12)",
                      color: "#7c3aed",
                    }}
                  >
                    ✓ Anchored on{" "}
                    {data.blockchain.chain === "polygon"
                      ? "Polygon"
                      : "Bitcoin"}
                  </span>
                  {data.blockchain.anchored_at && (
                    <span className="text-xs" style={{ color: "#6B7280" }}>
                      {formatDate(data.blockchain.anchored_at)}
                    </span>
                  )}
                </div>
                <div
                  className="text-xs space-y-1.5"
                  style={{ color: "#6B7280" }}
                >
                  <div>
                    <span style={{ color: "#94A3B8" }}>Block:</span>{" "}
                    <span className="font-mono">
                      {data.blockchain.block_number?.toLocaleString()}
                    </span>
                  </div>
                  <div className="break-all">
                    <span style={{ color: "#94A3B8" }}>Tx:</span>{" "}
                    <span className="font-mono">
                      {data.blockchain.tx_hash?.slice(0, 16)}…
                      {data.blockchain.tx_hash?.slice(-8)}
                    </span>
                  </div>
                </div>
                {data.blockchain.explorer_url && (
                  <a
                    href={data.blockchain.explorer_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block mt-2 px-4 py-2 rounded-lg text-xs font-semibold"
                    style={{ background: "#7c3aed", color: "white" }}
                  >
                    Verify on{" "}
                    {data.blockchain.chain === "polygon"
                      ? "PolygonScan"
                      : "Blockchain.com"}{" "}
                    →
                  </a>
                )}
                <details className="mt-3">
                  <summary
                    className="text-xs cursor-pointer"
                    style={{ color: "#6B7280" }}
                  >
                    Merkle proof (advanced)
                  </summary>
                  <pre
                    className="text-[10px] mt-2 p-2 rounded overflow-x-auto"
                    style={{ background: "#FFFFFF", color: "#6B7280" }}
                  >
                    {JSON.stringify(
                      {
                        leaf_hash: data.blockchain.leaf_hash,
                        merkle_proof: data.blockchain.merkle_proof,
                        expected_root: data.blockchain.merkle_root,
                      },
                      null,
                      2,
                    )}
                  </pre>
                </details>
              </div>
            ) : (
              <div className="px-5 py-4 text-xs" style={{ color: "#6B7280" }}>
                ⏳{" "}
                {data.blockchain.note ||
                  "Anchor pending — will be confirmed within 24 hours."}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="pt-6 pb-4 text-center animate-section">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div
              className="w-6 h-6 rounded-lg grid place-items-center"
              style={{ background: "#0A1F44" }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/aminra-mark.png" alt="AMINRA" className="w-4 h-4" />
            </div>
            <span className="text-xs font-bold" style={{ color: "#0A1F44" }}>
              AMINRA
            </span>
          </div>
          <p className="text-xs" style={{ color: "#94A3B8" }}>
            Powered by AMINRA
          </p>
          <p className="text-xs mt-1" style={{ color: "#CBD5E1" }}>
            Halal Certification Verification Platform
          </p>
        </div>
      </div>
    </div>
  );
}
