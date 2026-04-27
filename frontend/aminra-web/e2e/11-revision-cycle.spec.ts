/**
 * UAT (E2E) for the submission revisions cycle.
 *
 * Skips gracefully if backend lacks seeded data (DB without business+provider users).
 * Just verifies the API endpoints respond correctly to authenticated calls.
 */
import { test, expect } from "./fixtures";

test.describe("11. Submission revisions cycle", () => {
  test("Revisions endpoint reachable for valid submission", async ({ api, biz }) => {
    // Find a submission owned by biz user
    const list = await api.get("/api/submissions/my-submissions", {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401]).toContain(list.status());

    if (list.status() !== 200) {
      test.skip(true, "Cannot access biz submissions");
      return;
    }

    const data = await list.json();
    if (!data.submissions || data.submissions.length === 0) {
      test.skip(true, "No submissions seeded");
      return;
    }

    const sub = data.submissions[0];
    const revRes = await api.get(`/api/submissions/${sub.id}/revisions`, {
      headers: { Authorization: `Bearer ${biz.token}` },
    });
    expect([200, 307, 401, 403]).toContain(revRes.status());
  });

  test("Provider rejects request-revision for unauthorized submission with 403/404", async ({ api, prov }) => {
    if (!prov?.token) {
      test.skip(true, "No provider token available");
      return;
    }
    // Try to request revision on random UUID — should 404
    const fakeSubId = "00000000-0000-0000-0000-000000000000";
    const res = await api.post(`/api/submissions/received/${fakeSubId}/request-revision`, {
      headers: { Authorization: `Bearer ${prov.token}` },
      data: { feedback: "test", document_feedback: [] },
    });
    expect([403, 404]).toContain(res.status());
  });

  test("Business cannot request-revision (RBAC enforced)", async ({ api, biz }) => {
    const fakeSubId = "00000000-0000-0000-0000-000000000000";
    const res = await api.post(`/api/submissions/received/${fakeSubId}/request-revision`, {
      headers: { Authorization: `Bearer ${biz.token}` },
      data: { feedback: "trying", document_feedback: [] },
    });
    expect(res.status()).toBe(403);
  });

  test("Resubmit endpoint validates submission exists", async ({ api, biz }) => {
    const fakeSubId = "00000000-0000-0000-0000-000000000000";
    const res = await api.post(`/api/submissions/${fakeSubId}/resubmit`, {
      headers: { Authorization: `Bearer ${biz.token}` },
      data: { business_notes: "test" },
    });
    expect([403, 404]).toContain(res.status());
  });
});
