"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

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
  upload_required_documents: "Upload required documents",
  replace_rejected_documents: "Replace rejected documents",
  submit_capa_evidence: "Submit CAPA evidence",
};

const BOUND_READINESS_STATES = new Set([
  "requirements_pending",
  "documents_rejected",
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
  if (value === "bound") return "Bound";
  if (value === "unknown") return "UNKNOWN (legacy/unbound)";
  if (value === "unconfigured") return "Not configured";
  return "Binding state unavailable";
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
    return <section aria-label="Profile readiness"><p role="status">Loading Profile readiness…</p></section>;
  }
  if (error === "forbidden") {
    return <section aria-label="Profile readiness"><p role="alert">You are not authorized to view this dashboard.</p></section>;
  }
  if (!data) {
    return <section aria-label="Profile readiness"><p role="alert">Could not load Profile readiness. Please try again.</p><button type="button" onClick={() => setRefresh((n) => n + 1)}>Refresh</button></section>;
  }
  if (data.total_dossiers === 0 && data.state === "first_use") {
    return <section aria-label="Profile readiness"><h2>Get started</h2><p>No dossiers yet.</p><Link href="/dossiers/new">Create dossier</Link></section>;
  }

  const pageCount = Math.max(1, Math.ceil(data.total_dossiers / Math.max(1, Math.min(data.page_size, 50))));

  return (
    <section aria-label="Profile readiness">
      <header>
        <h2>Profile readiness</h2>
        <p>As of <time dateTime={data.as_of}>{data.as_of}</time></p>
        <button type="button" onClick={() => setRefresh((n) => n + 1)}>Refresh</button>
      </header>
      {loading && <p role="status">Loading updated Profile readiness…</p>}
      {stale && <p role="status">Showing partial, possibly stale data; refresh failed.</p>}
      {data.profiles.map((profile) => (
        <article key={profile.id ?? "unknown-profile"} aria-label={`${profile.name_vi ?? "Unknown Profile"} Profile`}>
          <h3>{profile.name_vi ?? "Unknown Profile"} {profile.code && <small>{profile.code}</small>} <small>— {profile.dossiers.length} on this page</small></h3>
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
            const businessAction = readiness?.next_actor_role === "business";
            const actionLabel = ACTION_LABELS[readiness?.next_action ?? ""] ?? "Open dossier";
            const dossierHref = `/dossiers/${encodeURIComponent(dossier.id)}`;

            return (
              <section key={dossier.id} aria-label={dossier.title}>
                <h4>{dossier.title}</h4>
                <p>Status: {bindingLabel(binding)}; requirements version: {versionId ?? "not bound"}</p>
                {readiness?.state === "requirements_no_required_slots" && <p>Published requirements contain no required slots; percentage is not applicable.</p>}
                {readiness?.state === "requirements_empty" && <p>Published requirements have no slots; percentage is not applicable.</p>}
                {known && readiness?.readiness_percent != null && <p>Readiness: {readiness.readiness_percent}%</p>}
                {slots.length > 0 && (
                  <ul aria-label={`${dossier.title} requirements`}>
                    {slots.map((slot, index) => (
                      <li key={`${slot.doc_type}-${index}`}>
                        {slot.doc_type} ({slot.required ? "required" : "optional"}): <strong>{slot.state}</strong>
                        {slot.requirements_version_id && <> — Requirements {slot.requirements_version_id}</>}
                        {slot.submission_id && <> — Submission {slot.submission_id}, round {slot.submitted_round ?? "unknown"}</>}
                        {slot.evidence_document_id && <> — Evidence {slot.evidence_document_id}{slot.evidence_version != null && `, version ${slot.evidence_version}`}</>}
                      </li>
                    ))}
                  </ul>
                )}
                {businessAction ? (
                  <Link href={dossierHref}>{actionLabel}</Link>
                ) : (
                  <><p>{readiness?.next_actor_role ? "Waiting for the next actor." : "Next action not specified."}</p><Link href={dossierHref}>Open dossier</Link></>
                )}
              </section>
            );
          })}
        </article>
      ))}
      <p>Showing {data.profiles.reduce((sum, profile) => sum + profile.dossiers.length, 0)} dossiers on this page (page-scoped); {data.total_dossiers} total.</p>
      <nav aria-label="Dashboard pagination">
        <button type="button" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous page</button>
        <span>Page {page} of {pageCount}</span>
        <button type="button" disabled={page >= pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}>Next page</button>
      </nav>
    </section>
  );
}
