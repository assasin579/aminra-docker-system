export default function ConflictsPage() {
  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="conflict-interest-register-page">
      <header className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-700">CB Trust Core</p>
        <h1 className="text-3xl font-bold">Conflict-of-Interest Register</h1>
        <p className="mt-2 text-gray-600">
          Declare, review, clear, block, and override conflicts before audit assignment or certification decisions.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-2" aria-label="Conflict declaration">
        <form className="rounded-lg border bg-white p-4 shadow-sm" data-api-path="/api/conflicts" data-method="POST">
          <h2 className="mb-3 text-xl font-semibold">Declare conflict</h2>
          <label className="block text-sm font-medium" htmlFor="business_tenant">
            Business tenant
          </label>
          <input id="business_tenant" name="business_tenant" className="mb-3 mt-1 w-full rounded border p-2" required />

          <label className="block text-sm font-medium" htmlFor="person_user_id">
            Person user ID
          </label>
          <input id="person_user_id" name="person_user_id" className="mb-3 mt-1 w-full rounded border p-2" required />

          <label className="block text-sm font-medium" htmlFor="person_role">
            Role
          </label>
          <select id="person_role" name="person_role" className="mb-3 mt-1 w-full rounded border p-2" defaultValue="auditor">
            <option value="auditor">Auditor</option>
            <option value="reviewer">Reviewer</option>
            <option value="decision_maker">Decision maker</option>
            <option value="cb_admin">CB admin</option>
          </select>

          <label className="block text-sm font-medium" htmlFor="conflict_type">
            Conflict type
          </label>
          <select id="conflict_type" name="conflict_type" className="mb-3 mt-1 w-full rounded border p-2" defaultValue="prior_employment">
            <option value="prior_employment">Prior employment</option>
            <option value="consultancy">Consultancy</option>
            <option value="financial_interest">Financial interest</option>
            <option value="family_relationship">Family relationship</option>
            <option value="ownership">Ownership</option>
            <option value="other">Other</option>
          </select>

          <label className="block text-sm font-medium" htmlFor="description">
            Description
          </label>
          <textarea id="description" name="description" className="mb-3 mt-1 w-full rounded border p-2" required />
          <button className="rounded bg-amber-700 px-4 py-2 font-semibold text-white" type="submit">
            Submit declaration
          </button>
        </form>

        <aside className="rounded-lg border bg-amber-50 p-4" data-testid="conflict-controls-contract">
          <h2 className="mb-3 text-xl font-semibold">Required controls</h2>
          <ul className="list-disc space-y-2 pl-5 text-sm">
            <li data-marker="unresolved-conflicts-block">Declared, under-review, and blocked conflicts block assignments and decisions.</li>
            <li data-marker="cleared-conflicts-allow">Cleared conflicts allow work to proceed.</li>
            <li data-marker="overridden-conflicts-audit">Overrides allow work only with owner/admin approval and audit logging.</li>
            <li data-marker="cross-provider-scope">Provider scope is isolated by canonical provider ID.</li>
          </ul>
        </aside>
      </section>

      <section className="mt-6 rounded-lg border bg-white p-4 shadow-sm" aria-label="Review and override">
        <h2 className="mb-3 text-xl font-semibold">Review / override</h2>
        <form className="grid gap-3 md:grid-cols-3" data-api-path="/api/conflicts/{id}/review" data-method="POST">
          <input name="conflict_id" aria-label="Conflict ID" className="rounded border p-2" placeholder="Conflict ID" required />
          <select name="status" aria-label="Review status" className="rounded border p-2" defaultValue="cleared">
            <option value="under_review">Under review</option>
            <option value="cleared">Cleared</option>
            <option value="blocked">Blocked</option>
          </select>
          <input name="review_reason" aria-label="Review reason" className="rounded border p-2" placeholder="Review reason (required)" required />
        </form>
        <form className="mt-3 grid gap-3 md:grid-cols-2" data-api-path="/api/conflicts/{id}/override" data-method="POST">
          <input name="override_conflict_id" aria-label="Override conflict ID" className="rounded border p-2" placeholder="Conflict ID" required />
          <input
            name="override_reason"
            aria-label="Override reason"
            className="rounded border p-2"
            placeholder="Override reason (required)"
            required
            data-testid="conflict-override-reason-required"
          />
        </form>
      </section>
    </main>
  );
}
