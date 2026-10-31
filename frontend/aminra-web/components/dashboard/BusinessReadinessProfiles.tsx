"use client";

import Link from "next/link";
import { DOC_TYPE_LABEL_VI } from "@/lib/dossierWorkflow";
import { useEffect, useRef, useState } from "react";
import welcome from "./DossierWelcome.module.css";

type Slot = {
  doc_type: string;
  required: boolean;
  state: string;
  evidence_document_id?: string | null;
  evidence_version?: number | null;
  requirements_version_id?: string | null;
  submission_id?: string | null;
  submitted_round?: number | null;
};

type Dossier = {
  id: string;
  title: string;
  requirements_version_number?: number | null;
  requirements_version_id?: string | null;
  requirements_binding_status?: string | null;
  readiness?: {
    state?: string;
    readiness_percent?: number | null;
    requirements_version_id?: string | null;
    requirements_binding_status?: string | null;
    requirement_slots?: Slot[];
    next_action?: string | null;
    next_actor_role?: string | null;
  };
};

type Dashboard = {
  state: "first_use" | "ready";
  as_of: string;
  page: number;
  page_size: number;
  total_dossiers: number;
  profiles: Array<{
    id: string | null;
    code: string | null;
    name_vi: string | null;
    dossiers: Dossier[];
  }>;
};

const ACTION_LABELS: Record<string, string> = {
  respond_to_revision: "Xem yêu cầu sửa",
  submit_dossier_to_cb: "Gửi hồ sơ cho đơn vị chứng nhận",
  upload_required_documents: "Bổ sung tài liệu",
  replace_rejected_documents: "Sửa tài liệu bị trả lại",
  submit_capa_evidence: "Bổ sung bằng chứng khắc phục",
};

const BOUND_READINESS_STATES = new Set([
  "requirements_pending",
  "documents_rejected",
  "documents_ready_to_submit",
  "revision_required",
  "documents_in_review",
  "ncr_open",
  "capa_in_review",
  "ready_for_decision",
  "certificate_pending",
  "certified",
]);

function parseDashboard(value: unknown): Dashboard {
  if (!value || typeof value !== "object") throw new Error("Invalid dashboard response");
  const result = value as Partial<Dashboard>;
  if (
    !["first_use", "ready"].includes(result.state ?? "") ||
    typeof result.as_of !== "string" ||
    !Number.isInteger(result.page) ||
    !Number.isInteger(result.page_size) ||
    typeof result.total_dossiers !== "number" ||
    result.total_dossiers < 0 ||
    !Array.isArray(result.profiles)
  ) throw new Error("Invalid dashboard response");
  if ((result.total_dossiers === 0) !== (result.state === "first_use")) {
    throw new Error("Inconsistent dashboard response");
  }
  return result as Dashboard;
}

function bindingLabel(value?: string | null): string {
  if (value === "bound") return "Đã chốt yêu cầu";
  if (value === "unknown") return "Chưa xác định bộ yêu cầu";
  if (value === "unconfigured") return "Chờ công bố yêu cầu";
  return "Chưa có thông tin yêu cầu";
}

export default function BusinessReadinessProfiles({ token, contextKey }: { token: string | null; contextKey: string }) {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<"forbidden" | "failure" | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [stale, setStale] = useState(false);
  const dataRef = useRef<Dashboard | null>(null);
  const lastContext = useRef(`${token ?? ""}:${contextKey}`);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const requestContext = `${token ?? ""}:${contextKey}`;
    const contextChanged = lastContext.current !== requestContext;
    lastContext.current = requestContext;

    if (contextChanged) {
      dataRef.current = null;
      setData(null);
      setStale(false);
      setPage(1);
    }

    if (!token) {
      dataRef.current = null;
      setData(null);
      setError("failure");
      setStale(false);
      setLoading(false);
      return () => {
        active = false;
        controller.abort();
      };
    }

    const hadSameScopeData = !contextChanged && dataRef.current !== null;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const query = new URLSearchParams({ page: String(page), page_size: "20" });
        const response = await fetch(`/api/dossiers/dashboard?${query.toString()}`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (response.status === 401 || response.status === 403) {
          if (!active) return;
          dataRef.current = null;
          setData(null);
          setError("forbidden");
          setStale(false);
          return;
        }
        if (!response.ok) throw new Error("Dashboard request failed");
        const parsed = parseDashboard(await response.json());
        if (!active) return;
        dataRef.current = parsed;
        setData(parsed);
        setError(null);
        setStale(false);
      } catch {
        if (!active || controller.signal.aborted) return;
        setError("failure");
        setStale(hadSameScopeData);
        if (!hadSameScopeData) {
          dataRef.current = null;
          setData(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
      controller.abort();
    };
  }, [token, contextKey, page, refresh]);

  if (loading && !data) {
    return <section className="rounded-2xl border border-cream-300 bg-white p-5 text-navy-900 space-y-4" aria-label="Mức sẵn sàng hồ sơ"><p role="status">Đang tải mức sẵn sàng hồ sơ…</p></section>;
  }
  if (error === "forbidden") {
    return <section className="rounded-2xl border border-cream-300 bg-white p-5 text-navy-900 space-y-4" aria-label="Mức sẵn sàng hồ sơ"><p role="alert">Bạn không có quyền xem các hồ sơ này.</p></section>;
  }
  if (!data) {
    return <section className="rounded-2xl border border-cream-300 bg-white p-5 text-navy-900 space-y-4" aria-label="Mức sẵn sàng hồ sơ"><p role="alert">Không tải được hồ sơ. Vui lòng thử lại.</p><button className="rounded-lg border border-cream-300 px-3 py-2 text-navy-900 disabled:opacity-50 hover:bg-cream-100 focus-visible:outline-2 focus-visible:outline-navy-700" type="button" onClick={() => setRefresh((n) => n + 1)}>Tải lại</button></section>;
  }
  if (data.total_dossiers === 0 && data.state === "first_use") {
    return (
      <section className={welcome.card} aria-labelledby="dossier-welcome-heading">
        <div>
          <p className={welcome.eyebrow}>HÀNH TRÌNH CHỨNG NHẬN</p>
          <h2 id="dossier-welcome-heading" className={welcome.title}>Bắt đầu hồ sơ chứng nhận</h2>
          <p className={welcome.description}>Từ bộ yêu cầu đến kết quả đánh giá — theo dõi hành trình chứng nhận trong một hồ sơ.</p>
          <Link href="/dossiers/new" className={welcome.action}>Tạo hồ sơ<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg></Link>
          <ol className={welcome.steps} aria-label="Các bước chuẩn bị hồ sơ">
            {["Chọn tiêu chuẩn", "Bổ sung tài liệu", "Gửi đánh giá"].map((label, index) => <li className={welcome.step} key={label}><span className={welcome.number} aria-hidden="true">{index + 1}</span>{label}</li>)}
          </ol>
        </div>
        <svg className={welcome.art} viewBox="0 0 240 210" fill="none" aria-hidden="true" focusable="false">
          <circle cx="125" cy="108" r="84" stroke="var(--cream-300)" strokeDasharray="3 8" />
          <g className={welcome.sheet}>
            <rect x="67" y="31" width="118" height="151" rx="12" transform="rotate(8 67 31)" fill="var(--cream-200)" stroke="var(--cream-300)" />
            <rect x="52" y="30" width="118" height="151" rx="12" transform="rotate(-5 52 30)" fill="var(--cream-50)" stroke="var(--cream-300)" />
            <rect x="58" y="26" width="118" height="151" rx="12" fill="white" stroke="var(--cream-300)" />
            <rect x="76" y="46" width="25" height="5" rx="2.5" fill="var(--gold-500)" />
            <path d="M76 67h74M76 81h60M76 104h74M76 118h74M76 132h47" stroke="var(--navy-100)" strokeWidth="5" strokeLinecap="round" />
            <path d="M76 153h31" stroke="var(--navy-700)" strokeWidth="3" strokeLinecap="round" />
          </g>
          <g className={welcome.seal}>
            <circle cx="177" cy="153" r="28" fill="var(--cream-50)" stroke="var(--gold-500)" strokeWidth="2" />
            <circle cx="177" cy="153" r="21" stroke="var(--gold-300)" />
            <path className={welcome.check} d="m165 153 8 8 16-18" stroke="var(--navy-900)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        </svg>
      </section>
    );
  }

  const pageCount = Math.max(1, Math.ceil(data.total_dossiers / Math.max(1, Math.min(data.page_size, 50))));

  return (
    <section className="rounded-2xl border border-cream-300 bg-white p-5 text-navy-900 space-y-4" aria-label="Mức sẵn sàng hồ sơ">
      <header>
        <h2 className="font-bold text-lg">Mức sẵn sàng hồ sơ</h2>
        <p>Cập nhật lúc <time dateTime={data.as_of}>{data.as_of}</time></p>
        <button className="rounded-lg border border-cream-300 px-3 py-2 text-navy-900 disabled:opacity-50 hover:bg-cream-100 focus-visible:outline-2 focus-visible:outline-navy-700" type="button" onClick={() => setRefresh((n) => n + 1)}>Tải lại</button>
      </header>
      {loading && <p role="status">Đang cập nhật hồ sơ…</p>}
      {stale && <p role="status">Cập nhật chưa thành công; thông tin đang hiển thị có thể đã cũ.</p>}
      {data.profiles.map((profile) => (
        <article className="space-y-3" key={profile.id ?? "unknown-profile"} aria-label={`${profile.name_vi ?? "Chưa xác định tiêu chuẩn"} Profile`}>
          <h3 className="font-semibold">{profile.name_vi ?? "Chưa xác định tiêu chuẩn"} {profile.code && <small>{profile.code}</small>} <small>— {profile.dossiers.length} hồ sơ trên trang này</small></h3>
          {profile.dossiers.map((dossier) => {
            const readiness = dossier.readiness;
            const binding = readiness?.requirements_binding_status ?? dossier.requirements_binding_status;
            const versionId = readiness?.requirements_version_id ?? dossier.requirements_version_id;
            const slots = readiness?.requirement_slots ?? [];
            const known = Boolean(
              readiness &&
              BOUND_READINESS_STATES.has(readiness.state ?? "") &&
              binding === "bound" &&
              versionId &&
              slots.some((slot) => slot.required),
            );
            const businessAction = ["business", "business_owner"].includes(readiness?.next_actor_role ?? "");
            const actionLabel = ACTION_LABELS[readiness?.next_action ?? ""] ?? "Xem hồ sơ";
            const dossierHref = `/dossiers/${encodeURIComponent(dossier.id)}`;

            return (
              <section className="rounded-xl border border-cream-300 bg-cream-100 p-4 space-y-2" key={dossier.id} aria-label={dossier.title}>
                <h4 className="font-semibold">{dossier.title}</h4>
                <p className="text-sm text-ink-500">{bindingLabel(binding)}{dossier.requirements_version_number != null && ` · Phiên bản yêu cầu ${dossier.requirements_version_number}`}</p>
                {readiness?.state === "requirements_no_required_slots" && <p>Bộ yêu cầu chưa có tài liệu bắt buộc; chưa áp dụng tỷ lệ sẵn sàng.</p>}
                {readiness?.state === "requirements_empty" && <p>Bộ yêu cầu đang trống; chưa áp dụng tỷ lệ sẵn sàng.</p>}
                {known && readiness?.readiness_percent != null && <p>Mức sẵn sàng: {readiness.readiness_percent}%</p>}
                {slots.length > 0 && (
                  <ul className="space-y-1 text-sm" aria-label={`${dossier.title} requirements`}>
                    {slots.map((slot, index) => (
                      <li key={`${slot.doc_type}-${index}`}>
                        {DOC_TYPE_LABEL_VI[slot.doc_type] ?? slot.doc_type} ({slot.required ? "bắt buộc" : "tùy chọn"}): <strong>{({ ready_to_submit: "Đã chuẩn bị — chưa gửi", missing_required: "Còn thiếu", pending_review: "Chờ đánh giá", approved: "Đã được duyệt", revision_required: "Cần sửa", optional_not_submitted: "Chưa nộp" } as Record<string, string>)[slot.state] ?? "Chưa xác định"}</strong>

                        {slot.submitted_round != null && <> · Vòng đánh giá {slot.submitted_round}</>}
                        {slot.evidence_version != null && <> · Tài liệu phiên bản {slot.evidence_version}</>}
                      </li>
                    ))}
                  </ul>
                )}
                {businessAction ? (
                  <Link href={dossierHref}>{actionLabel}</Link>
                ) : (
                  <><p>{readiness?.next_actor_role ? "Đang chờ bên phụ trách xử lý." : "Chưa xác định bước tiếp theo."}</p><Link href={dossierHref}>Xem hồ sơ</Link></>
                )}
              </section>
            );
          })}
        </article>
      ))}
      <p className="text-sm text-ink-500">Trang này: {data.profiles.reduce((sum, profile) => sum + profile.dossiers.length, 0)} hồ sơ · Tổng cộng: {data.total_dossiers} hồ sơ.</p>
      <nav className="flex flex-wrap items-center gap-3 text-sm" aria-label="Phân trang hồ sơ">
        <button className="rounded-lg border border-cream-300 px-3 py-2 text-navy-900 disabled:opacity-50 hover:bg-cream-100 focus-visible:outline-2 focus-visible:outline-navy-700" type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Trang trước</button>
        <span>Trang {page} / {pageCount}</span>
        <button className="rounded-lg border border-cream-300 px-3 py-2 text-navy-900 disabled:opacity-50 hover:bg-cream-100 focus-visible:outline-2 focus-visible:outline-navy-700" type="button" disabled={page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>Trang sau</button>
      </nav>
    </section>
  );
}
