import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ComplaintsPage from "@/app/complaints/page";
import ConflictsPage from "@/app/conflicts/page";
import type { UserProfile } from "@/components/UserAuthContext";

const { session } = vi.hoisted(() => ({ session: { user: null as UserProfile | null, token: "synthetic-token", loading: false } }));
vi.mock("@/components/UserAuthContext", () => ({ useUserAuth: () => session }));
const fetchMock = vi.fn();
function user(role: "provider" | "business", owner: boolean): UserProfile {
  return { id: "synthetic-user", email: "synthetic@example.invalid", role, status: "active", tenant_id: "synthetic-tenant", is_owner: owner, company_name: "Synthetic", company_code: null, realm_roles: ["cb_admin"] };
}
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => vi.unstubAllGlobals());

it("a provider member cannot review or override conflicts even if its realm role still lists cb_admin", async () => {
  session.user = user("provider", false);
  fetchMock.mockResolvedValue(Response.json({ conflicts: [] }));
  render(<ConflictsPage />);
  await screen.findByText("No declarations found.");
  expect(screen.getByRole("button", { name: "Submit declaration" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save review" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Override conflict" })).toBeNull();
});

it("business users cannot load a provider conflict register", () => {
  session.user = user("business", true);
  render(<ConflictsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("Provider access required.");
  expect(fetchMock).not.toHaveBeenCalled();
});

it("provider members cannot load an owner complaint queue", () => {
  session.user = user("provider", false);
  render(<ComplaintsPage />);
  expect(screen.getByRole("alert")).toHaveTextContent("Business or provider owner access required.");
  expect(fetchMock).not.toHaveBeenCalled();
});
