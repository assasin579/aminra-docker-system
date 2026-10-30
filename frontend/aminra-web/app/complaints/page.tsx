export default function ComplaintsAppealsPage() {
  return (
    <main className="mx-auto max-w-6xl p-6" data-testid="complaints-appeals-page">
      <header className="mb-6">
        <p className="text-sm font-semibold uppercase tracking-wide text-amber-700">CB Trust Core</p>
        <h1 className="text-3xl font-bold">Complaints & Appeals</h1>
        <p className="mt-2 text-gray-600">
          Track complaint intake, appeal independence, owner assignment, lifecycle transitions, and closure rationale.
        </p>
      </header>

      <section className="rounded-lg border bg-white p-4 shadow-sm" data-testid="complaint-queue" data-api-path="/api/complaints">
        <h2 className="mb-3 text-xl font-semibold">Complaint queue</h2>
        <ul className="list-disc space-y-2 pl-5 text-sm">
          <li data-marker="complaint-queue">Received, acknowledged, investigation, decision, and closure statuses are visible here.</li>
          <li data-marker="appeal-original-decision-requirement">Appeals require an original certification decision before submission.</li>
          <li data-marker="independent-appeal-handler">Appeal handler cannot be the original decision maker or linked audit auditor.</li>
        </ul>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2" aria-label="Create complaint or appeal">
        <form className="rounded-lg border bg-white p-4 shadow-sm" data-api-path="/api/complaints" data-method="POST">
          <h2 className="mb-3 text-xl font-semibold">Create case</h2>
          <label className="block text-sm font-medium" htmlFor="case_type">Case type</label>
          <select id="case_type" name="case_type" className="mb-3 mt-1 w-full rounded border p-2" defaultValue="complaint_service">
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
            data-testid="appeal-original-decision-required"
          />

          <label className="block text-sm font-medium" htmlFor="title">Title</label>
          <input id="title" name="title" className="mb-3 mt-1 w-full rounded border p-2" required />
          <label className="block text-sm font-medium" htmlFor="description">Description</label>
          <textarea id="description" name="description" className="mb-3 mt-1 w-full rounded border p-2" required />
          <button className="rounded bg-amber-700 px-4 py-2 font-semibold text-white" type="submit">Submit case</button>
        </form>

        <form className="rounded-lg border bg-white p-4 shadow-sm" data-api-path="/api/complaints/{id}/assign" data-method="POST">
          <h2 className="mb-3 text-xl font-semibold">Assign owner</h2>
          <label className="block text-sm font-medium" htmlFor="owner_id">Owner user ID</label>
          <input id="owner_id" name="owner_id" className="mb-3 mt-1 w-full rounded border p-2" required data-testid="assignment-owner-field" />
          <input name="notes" className="mb-3 mt-1 w-full rounded border p-2" placeholder="Assignment notes" />
          <button className="rounded bg-amber-700 px-4 py-2 font-semibold text-white" type="submit">Assign</button>
        </form>
      </section>

      <section className="mt-6 rounded-lg border bg-white p-4 shadow-sm" aria-label="Transition controls" data-marker="transition-controls">
        <h2 className="mb-3 text-xl font-semibold">Transition controls</h2>
        <form className="grid gap-3 md:grid-cols-4" data-api-path="/api/complaints/{id}/transition" data-method="POST">
          <input name="case_id" aria-label="Case ID" className="rounded border p-2" placeholder="Case ID" required />
          <select name="to_status" aria-label="To status" className="rounded border p-2" defaultValue="acknowledged">
            <option value="acknowledged">Acknowledge</option>
            <option value="under_investigation">Under investigation</option>
            <option value="decision_made">Decision made</option>
            <option value="closed">Closed</option>
            <option value="rejected">Rejected</option>
          </select>
          <input name="decision_summary" className="rounded border p-2" placeholder="Decision summary (required for decision_made)" />
          <input name="closure_reason" className="rounded border p-2" placeholder="Closure reason (required to close)" required data-testid="closure-reason-required" />
        </form>
      </section>

      <section className="mt-6 rounded-lg border bg-amber-50 p-4" data-api-path="/api/complaints/{id}/events">
        <h2 className="mb-3 text-xl font-semibold">Case events</h2>
        <p className="text-sm" data-marker="append-only-events">Notes and lifecycle transitions append to complaint_case_events.</p>
      </section>
    </main>
  );
}
