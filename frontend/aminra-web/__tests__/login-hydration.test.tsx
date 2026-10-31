import { act, fireEvent, waitFor } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { hydrateRoot, type Root } from "react-dom/client";
import { beforeEach, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import BusinessLoginPage from "@/app/(auth)/business/login/page";
import ProviderLoginPage from "@/app/(auth)/provider/login/page";

const { business, provider, replace } = vi.hoisted(() => ({ business: vi.fn(), provider: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));
vi.mock("@/components/UserAuthContext", () => ({ useUserAuth: () => ({ loginBusiness: business, loginProvider: provider }) }));
beforeEach(() => { vi.clearAllMocks(); business.mockResolvedValue(undefined); provider.mockResolvedValue(undefined); });

for (const [name, Page, login] of [["business", BusinessLoginPage, business], ["provider", ProviderLoginPage, provider]] as const) {
  it(`${name} server-rendered credentials cannot be edited before event handlers hydrate`, () => {
    const container = document.createElement("div");
    container.innerHTML = renderToString(<Page />);
    for (const selector of ['input[type="email"]', 'input[type="password"]', 'input[type="checkbox"]']) {
      expect(container.querySelector(selector)).toBeDisabled();
    }
  });
  it(`${name} hydrated credentials preserve typed values and submit exactly once`, async () => {
    const container = document.createElement("div");
    container.innerHTML = renderToString(<Page />); document.body.append(container);
    let root: Root | undefined;
    try {
      await act(async () => { root = hydrateRoot(container, <Page />); });
      const email = container.querySelector('input[type="email"]')!;
      const password = container.querySelector('input[type="password"]')!;
      await waitFor(() => expect(email).toBeEnabled());
      fireEvent.change(email, { target: { value: "synthetic@example.invalid" } });
      fireEvent.change(password, { target: { value: "synthetic-only" } });
      await act(async () => { fireEvent.submit(container.querySelector("form")!); });
      expect(email).toHaveValue("synthetic@example.invalid");
      expect(password).toHaveValue("synthetic-only");
      expect(login).toHaveBeenCalledExactlyOnceWith("synthetic@example.invalid", "synthetic-only", true);
      expect(replace).toHaveBeenCalledWith("/dashboard/" + name);
    } finally { if (root) await act(async () => root!.unmount()); container.remove(); }
  });
}
