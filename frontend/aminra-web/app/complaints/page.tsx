"use client";

import { useEffect, useState } from "react";
import { useUserAuth, type UserProfile } from "@/components/UserAuthContext";
import { apiJson } from "@/lib/apiClient";
import { Feedback, Field, fieldClass, formValues, useTrustRegister } from "@/components/trust/TrustRegister";

type Case = { id: string; title: string; description: string; status: string; provider_id: string; assigned_owner_id?: string; decision_summary?: string; closure_reason?: string };
type Provider = { id: string; company_name: string; email: string };

export default function ComplaintsAppealsPage() {
  const { user, token, loading } = useUserAuth();
  if (loading) return <p role="status">Loading session…</p>;
  if (!user || !token) return <p role="alert">Sign in to access complaints.</p>;
  if (user.role !== "business" && !(user.role === "provider" && user.is_owner)) return <p role="alert">Business or provider owner access required.</p>;
  return <ComplaintRegister key={user.id} user={user} token={token} />;
}

function ComplaintRegister({ user, token }: { user: UserProfile; token: string }) {
  const register = useTrustRegister<Case>("/api/api/complaints", "cases", token);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerError, setProviderError] = useState("");
  const [caseType, setCaseType] = useState("complaint_service");
  const [transition, setTransition] = useState("acknowledged");
  const isBusiness = user.role === "business";
  useEffect(() => {
    if (!isBusiness) return;
    let active = true;
    apiJson<{ providers: Provider[] }>("/api/api/submissions/providers", { token }).then(data => {
      if (!Array.isArray(data.providers)) throw new Error("Invalid provider list.");
      if (active) setProviders(data.providers);
    }).catch(e => { if (active) setProviderError(e instanceof Error ? e.message : "Unable to load providers."); });
    return () => { active = false; };
  }, [token, isBusiness]);
  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="complaints-appeals-page">
      <header className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-700">CB Trust Core</p>
        <h1 className="text-3xl font-bold">Complaints & Appeals</h1>
        <p className="mt-2 text-gray-600">
          Track complaint intake, appeal independence, owner assignment, lifecycle transitions, and closure rationale.
        </p>
      </header>

      <Feedback {...register} />
      <section className="rounded-lg border bg-white p-4 shadow-sm" data-testid="complaint-queue" data-api-path="/api/complaints">
        <h2 className="mb-3 text-xl font-semibold">Complaint queue</h2>
        {!register.loading && !register.rows.length && <p>No cases found.</p>}
        <ul className="space-y-3">{register.rows.map(row => <li key={row.id} data-testid={`case-${row.id}`} className="break-words rounded border p-3">
          <h3 className="font-semibold">{row.title}</h3><p>{row.description}</p><p>Case ID: {row.id}</p><p>Status: {row.status}</p>
          <p>Provider: {row.provider_id}</p>{row.assigned_owner_id && <p>Owner: {row.assigned_owner_id}</p>}
          {row.decision_summary && <p>Decision: {row.decision_summary}</p>}{row.closure_reason && <p>Closure: {row.closure_reason}</p>}
        </li>)}</ul>
        <ul className="list-disc space-y-2 pl-5 text-sm">
          <li data-marker="complaint-queue">The queue displays the current saved case state.</li>
          <li data-marker="appeal-original-decision-requirement">Appeals require an original certification decision before submission.</li>
          <li data-marker="independent-appeal-handler">Appeal handler cannot be the original decision maker or linked audit auditor.</li>
        </ul>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2" aria-label="Create complaint or appeal">
        <form className="rounded-lg border bg-white p-4 shadow-sm" data-api-path="/api/complaints" data-method="POST" onSubmit={event => {
          const values = formValues(event);
          const form = event.currentTarget;
          void register.mutate("/api/api/complaints", { ...values, source: isBusiness ? "business" : "provider", original_decision_id: values.original_decision_id || null, business_tenant: values.business_tenant || null }).then(saved => {
            if (saved) { form.reset(); setCaseType("complaint_service"); }
          });
        }}><fieldset disabled={register.pending || register.loading || register.uncertain}>
          <h2 className="mb-3 text-xl font-semibold">Create case</h2>
          {isBusiness ? <><Field name="provider_id" label="Certification provider"><select name="provider_id" className={fieldClass} required defaultValue="">
            <option value="" disabled>Select a provider</option>{providers.map(p => <option key={p.id} value={p.id}>{p.company_name || p.email} ({p.email})</option>)}
          </select></Field>{providerError && <p role="alert">{providerError} Reload to retry.</p>}</> : <Field name="business_tenant" label="Business tenant" placeholder="Optional business tenant ID" />}
          <label className="block text-sm font-medium" htmlFor="case_type">Case type</label>
          <select id="case_type" name="case_type" className="mb-3 mt-1 w-full rounded border p-2" value={caseType} onChange={e => setCaseType(e.target.value)}>
            <option value="complaint_service">Service complaint</option>
            <option value="complaint_certified_client">Certified client complaint</option>
            <option value="appeal_decision">Appeal decision</option>
          </select>

          <label className="block text-sm font-medium" htmlFor="original_decision_id">Original decision ID</label>
          <input
            id="original_decision_id"
            name="original_decision_id"
            className="mb-3 mt-1 w-full rounded border p-2"
            placeholder="Required for appeal_decision"
            required={caseType === "appeal_decision"}
            data-testid="appeal-original-decision-required"
          />

          <label className="block text-sm font-medium" htmlFor="title">Title</label>
          <input id="title" name="title" className="mb-3 mt-1 w-full rounded border p-2" required />
          <label className="block text-sm font-medium" htmlFor="description">Description</label>
          <textarea id="description" name="description" className="mb-3 mt-1 w-full rounded border p-2" required />
          <button className="rounded bg-amber-700 px-4 py-2 font-semibold text-white" type="submit" disabled={isBusiness && !providers.length}>Submit case</button>
        </fieldset></form>

        {!isBusiness && <form className="rounded-lg border bg-white p-4 shadow-sm" data-api-path="/api/complaints/{id}/assign" data-method="POST" onSubmit={event => {
          const { case_id, ...values } = formValues(event); void register.mutate(`/api/api/complaints/${encodeURIComponent(case_id)}/assign`, values);
        }}><fieldset disabled={register.pending || register.loading || register.uncertain}>
          <h2 className="mb-3 text-xl font-semibold">Assign owner</h2>
          <Field name="case_id" label="Assignment case ID" required />
          <label className="block text-sm font-medium" htmlFor="owner_id">Owner user ID</label>
          <input id="owner_id" name="owner_id" className="mb-3 mt-1 w-full rounded border p-2" required data-testid="assignment-owner-field" />
          <input name="notes" aria-label="Assignment notes" className="mb-3 mt-1 w-full rounded border p-2" placeholder="Assignment notes" />
          <button className="rounded bg-amber-700 px-4 py-2 font-semibold text-white" type="submit">Assign</button>
        </fieldset></form>}
      </section>

      {!isBusiness && <section className="mt-6 rounded-lg border bg-white p-4 shadow-sm" aria-label="Transition controls" data-marker="transition-controls">
        <h2 className="mb-3 text-xl font-semibold">Transition controls</h2>
        <form data-api-path="/api/complaints/{id}/transition" data-method="POST" onSubmit={event => {
          const { case_id, ...values } = formValues(event);
          const current = register.rows.find(row => row.id === case_id);
          if (!current) {
            const input = event.currentTarget.elements.namedItem("case_id") as HTMLInputElement;
            input.setCustomValidity("Reload the queue and enter an existing case ID before changing status.");
            input.reportValidity();
            return;
          }
          void register.mutate(`/api/api/complaints/${encodeURIComponent(case_id)}/transition`, {
            ...values,
            // Preserve saved rationale outside the transition that owns that field.
            decision_summary: values.to_status === "decision_made" ? values.decision_summary : current?.decision_summary || "",
            closure_reason: values.to_status === "closed" ? values.closure_reason : current?.closure_reason || "",
          });
        }}><fieldset className="grid gap-3 md:grid-cols-2" disabled={register.pending || register.loading || register.uncertain}>
          <input name="case_id" onChange={event => event.currentTarget.setCustomValidity("")} aria-label="Case ID" className="rounded border p-2" placeholder="Case ID" required />
          <select name="to_status" aria-label="To status" className="rounded border p-2" value={transition} onChange={e => setTransition(e.target.value)}>
            <option value="acknowledged">Acknowledge</option>
            <option value="under_investigation">Under investigation</option>
            <option value="decision_made">Decision made</option>
            <option value="closed">Closed</option>
            <option value="rejected">Rejected</option>
          </select>
          <input name="decision_summary" aria-label="Decision summary" required={transition === "decision_made"} className="rounded border p-2" placeholder="Decision summary (required for decision_made)" />
          <input name="closure_reason" aria-label="Closure reason" className="rounded border p-2" placeholder="Closure reason (required to close)" required={transition === "closed"} data-testid="closure-reason-required" />
          <button type="submit" className="rounded bg-amber-700 px-4 py-2 font-semibold text-white">Update case status</button>
        </fieldset></form>
      </section>}

      <section className="mt-6 rounded-lg border bg-amber-50 p-4">
        <h2 className="mb-3 text-xl font-semibold">Case history</h2>
        <p className="text-sm" data-marker="append-only-events">Lifecycle actions are recorded by the server in append-only case events. The queue displays current saved state.</p>
      </section>
    </main>
  );
}
