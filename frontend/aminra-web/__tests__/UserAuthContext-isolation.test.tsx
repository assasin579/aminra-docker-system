import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AdminAuthProvider, useAdminAuth } from "@/components/AdminAuthContext";
import { UserAuthProvider, useUserAuth, type UserProfile } from "@/components/UserAuthContext";

const { oidcGetUser } = vi.hoisted(() => ({ oidcGetUser: vi.fn() }));
vi.mock("@/lib/auth-oidc", () => ({ isOidcEnabled: () => true, getOidcUser: oidcGetUser, signoutRedirect: vi.fn(), signinRedirect: vi.fn() }));
const fetchMock = vi.fn();
function profile(id: string, owner = true): UserProfile {
  return { id, email: id + "@example.invalid", keycloak_sub: id, role: "business", status: "active", company_name: id, company_code: null, tenant_id: id, is_owner: owner };
}
function jwt(id: string) { return "header." + btoa(JSON.stringify({ sub: id, email: id + "@example.invalid" })).replace(/=/g, "") + ".signature"; }
function store(id: string) { localStorage.setItem("aminra_user_token", jwt(id)); localStorage.setItem("aminra_user_profile", JSON.stringify(profile(id))); }
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r; }); return { promise, resolve }; }
const wrapper = ({ children }: { children: ReactNode }) => <UserAuthProvider>{children}</UserAuthProvider>;
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); fetchMock.mockReset(); oidcGetUser.mockReset(); vi.stubGlobal("fetch", fetchMock); });
afterEach(() => vi.unstubAllGlobals());

it("clears an old identity while another tab's token is being verified", async () => {
  store("a"); const b = deferred<Response>();
  fetchMock.mockResolvedValueOnce(Response.json(profile("a"))).mockReturnValueOnce(b.promise);
  const { result } = renderHook(() => useUserAuth(), { wrapper });
  await waitFor(() => expect(result.current.user?.id).toBe("a"));
  act(() => { store("b"); window.dispatchEvent(new StorageEvent("storage", { key: "aminra_user_token", newValue: jwt("b") })); });
  expect(result.current.user).toBeNull(); expect(result.current.token).toBeNull();
  await act(async () => { b.resolve(Response.json(profile("b"))); });
  expect(result.current.user?.id).toBe("b"); expect(result.current.token).toBe(jwt("b"));
});

it("a delayed restore cannot replace a newer successful login", async () => {
  store("a"); const old = deferred<Response>();
  fetchMock.mockReturnValueOnce(old.promise).mockResolvedValueOnce(Response.json({ access_token: jwt("b"), user: profile("b") }));
  const { result } = renderHook(() => useUserAuth(), { wrapper });
  await act(async () => { await result.current.loginBusiness("b@example.invalid", "synthetic"); });
  await act(async () => { old.resolve(Response.json(profile("a"))); });
  expect(result.current.user?.id).toBe("b"); expect(JSON.parse(localStorage.getItem("aminra_user_profile")!).id).toBe("b");
});

it("a delayed profile refresh cannot contaminate the new token's stored profile", async () => {
  store("a"); const old = deferred<Response>();
  fetchMock.mockResolvedValueOnce(Response.json(profile("a"))).mockReturnValueOnce(old.promise).mockResolvedValueOnce(Response.json({ access_token: jwt("b"), user: profile("b") }));
  const { result } = renderHook(() => useUserAuth(), { wrapper });
  await waitFor(() => expect(result.current.user?.id).toBe("a"));
  let refresh!: Promise<void>; act(() => { refresh = result.current.refreshProfile(); });
  await act(async () => { await result.current.loginBusiness("b@example.invalid", "synthetic"); });
  await act(async () => { old.resolve(Response.json(profile("a"))); await refresh; });
  expect(result.current.user?.id).toBe("b"); expect(localStorage.getItem("aminra_user_token")).toBe(jwt("b"));
  expect(JSON.parse(localStorage.getItem("aminra_user_profile")!).id).toBe("b");
});

it("a delayed logout cannot purge a newer successful login", async () => {
  store("a"); const oidc = deferred<null>(); oidcGetUser.mockReturnValue(oidc.promise);
  fetchMock.mockResolvedValueOnce(Response.json(profile("a"))).mockResolvedValueOnce(Response.json({ access_token: jwt("b"), user: profile("b") }));
  const { result } = renderHook(() => useUserAuth(), { wrapper });
  await waitFor(() => expect(result.current.user?.id).toBe("a"));
  act(() => result.current.logout()); await waitFor(() => expect(oidcGetUser).toHaveBeenCalled());
  await act(async () => { await result.current.loginBusiness("b@example.invalid", "synthetic"); oidc.resolve(null); });
  expect(localStorage.getItem("aminra_user_token")).toBe(jwt("b")); expect(result.current.user?.id).toBe("b");
});

it("a permission downgrade remounts cached privileged descendants", async () => {
  store("a"); fetchMock.mockResolvedValueOnce(Response.json(profile("a"))).mockResolvedValueOnce(Response.json(profile("a", false)));
  function Cached({ owner }: { owner: boolean }) { const [snapshot] = useState(owner ? "owner-cache" : "member-cache"); return <p>{snapshot}</p>; }
  function View() { const { user, refreshProfile } = useUserAuth(); return user && <><Cached owner={user.is_owner} /><button onClick={() => void refreshProfile()}>Refresh permissions</button></>; }
  render(<UserAuthProvider><View /></UserAuthProvider>);
  await screen.findByText("owner-cache"); fireEvent.click(screen.getByText("Refresh permissions"));
  await screen.findByText("member-cache"); expect(screen.queryByText("owner-cache")).toBeNull();
});

it("a mismatch cleanup finishing late cannot sign out the newer identity", async () => {
  store("a"); const cleanup = deferred<boolean>(); const erase = vi.fn(() => cleanup.promise);
  vi.stubGlobal("caches", { keys: async () => ["aminra-private"], delete: erase });
  fetchMock.mockResolvedValueOnce(Response.json(profile("a"))).mockResolvedValueOnce(Response.json(profile("a")))
    .mockResolvedValueOnce(Response.json({ access_token: jwt("b"), user: profile("b") }));
  const { result } = renderHook(() => useUserAuth(), { wrapper });
  await waitFor(() => expect(result.current.user?.id).toBe("a"));
  let mismatch!: Promise<unknown>; act(() => { mismatch = result.current.loginViaKeycloak(jwt("foreign")).catch(e => e); });
  await waitFor(() => expect(erase).toHaveBeenCalled());
  await act(async () => { await result.current.loginBusiness("b@example.invalid", "synthetic"); cleanup.resolve(true); await mismatch; });
  expect(result.current.user?.id).toBe("b"); expect(localStorage.getItem("aminra_user_token")).toBe(jwt("b"));
});

it("same-person realm-role downgrade discards cached admin descendants", async () => {
  const withRole = (role: string) => "header." + btoa(JSON.stringify({ sub: "a", email: "a@example.invalid", realm_access: { roles: [role] } })).replace(/=/g, "") + ".signature";
  const me = { ...profile("a"), role: "provider" };
  localStorage.setItem("aminra_user_token", withRole("platform_admin")); localStorage.setItem("aminra_user_profile", JSON.stringify(me));
  fetchMock.mockImplementation(async () => Response.json(me));
  function Cached({ admin }: { admin: boolean }) { const [snapshot] = useState(admin ? "admin-private-cache" : "provider-cache"); return <p>{snapshot}</p>; }
  function View() {
    const { user, token, loginViaKeycloak } = useUserAuth(); if (!user || !token) return null;
    const admin = JSON.parse(atob(token.split(".")[1])).realm_access.roles.includes("platform_admin");
    return <><Cached admin={admin} /><button onClick={() => void loginViaKeycloak(withRole("cb_admin"))}>Downgrade</button></>;
  }
  render(<UserAuthProvider><View /></UserAuthProvider>);
  await screen.findByText("admin-private-cache"); fireEvent.click(screen.getByText("Downgrade"));
  await screen.findByText("provider-cache"); expect(screen.queryByText("admin-private-cache")).toBeNull();
});

it("StrictMode effect replay still verifies and restores the active identity", async () => {
  store("a"); fetchMock.mockImplementation(async () => Response.json(profile("a")));
  const { result } = renderHook(() => useUserAuth(), { wrapper, reactStrictMode: true });
  await waitFor(() => expect(result.current.user?.id).toBe("a"));
  expect(result.current.loading).toBe(false);
});

it("server-confirmed admin downgrade clears cached admin data even while the JWT still lists admin", async () => {
  const t = "header." + btoa(JSON.stringify({sub:"a",email:"a@example.invalid",realm_access:{roles:["platform_admin","cb_admin"]}})).replace(/=/g,"") + ".signature";
  localStorage.setItem("aminra_user_token",t);
  const base = {...profile("a"),role:"provider"};
  fetchMock.mockResolvedValueOnce(Response.json({...base,realm_roles:["platform_admin","cb_admin"]})).mockResolvedValueOnce(Response.json({...base,realm_roles:["cb_admin"]}));
  function Cached({admin}:{admin:boolean}) { const [saved] = useState(admin ? "privileged-admin-records" : "provider-records"); return <p>{saved}</p>; }
  function View() { const {user,refreshProfile}=useUserAuth();const {isAdmin}=useAdminAuth();return user && <><Cached admin={isAdmin}/><button onClick={()=>void refreshProfile()}>Refresh authority</button></>; }
  render(<UserAuthProvider><AdminAuthProvider><View/></AdminAuthProvider></UserAuthProvider>);
  await screen.findByText("privileged-admin-records");fireEvent.click(screen.getByText("Refresh authority"));
  await screen.findByText("provider-records");expect(screen.queryByText("privileged-admin-records")).toBeNull();
});
