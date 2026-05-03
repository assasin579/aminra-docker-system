"use client";

import { useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "./Sidebar";
import { AdminAuthProvider } from "./AdminAuthContext";
import { UserAuthProvider, useUserAuth } from "./UserAuthContext";
import { FeatureFlagProvider } from "@/lib/featureFlags";

/**
 * Internal helper: reads JWT from UserAuthContext, passes to FeatureFlagProvider.
 * Must be rendered inside <UserAuthProvider>. Re-renders flags context when
 * the user logs in/out so closed-default behavior collapses cleanly.
 */
function FeatureFlagBootstrap({ children }: { children: ReactNode }) {
  const { token } = useUserAuth();
  return <FeatureFlagProvider token={token}>{children}</FeatureFlagProvider>;
}

const FULL_SCREEN_ROUTES = ["/landing", "/forgot-password", "/reset-password"];
const FULL_SCREEN_PREFIXES = [
  "/supplier-portal",
  "/invite",
  "/trace",
  "/verify",
  "/business/login",
  "/business/register",
  "/provider/login",
  "/provider/register",
  "/account/",
];

export default function LayoutShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  const isFullScreen =
    FULL_SCREEN_ROUTES.includes(pathname) ||
    FULL_SCREEN_PREFIXES.some((p) => pathname.startsWith(p));

  // Landing page — no sidebar, no padding, full screen
  if (isFullScreen) {
    return (
      <UserAuthProvider>
        <AdminAuthProvider>
          <FeatureFlagBootstrap>
            <div className="min-h-screen">{children}</div>
          </FeatureFlagBootstrap>
        </AdminAuthProvider>
      </UserAuthProvider>
    );
  }

  return (
    <UserAuthProvider>
      <AdminAuthProvider>
        <FeatureFlagBootstrap>
          <div className="flex min-h-screen lg:h-screen lg:overflow-hidden">
            {/* Mobile overlay */}
            {sidebarOpen && (
              <div
                className="fixed inset-0 bg-black/60 z-30 md:hidden animate-overlay"
                onClick={() => setSidebarOpen(false)}
              />
            )}

            {/* Sidebar — fixed width, no shrink */}
            <div
              className={`fixed inset-y-0 left-0 z-40 w-64 flex-shrink-0 transition-transform duration-300 md:relative md:translate-x-0 ${
                sidebarOpen
                  ? "translate-x-0"
                  : "-translate-x-full md:translate-x-0"
              }`}
            >
              <Sidebar onClose={() => setSidebarOpen(false)} />
            </div>

            {/* Main content — takes remaining space */}
            <div className="flex-1 min-w-0 flex flex-col lg:min-h-0 lg:overflow-hidden">
              {/* Mobile header */}
              <header
                className="md:hidden flex items-center px-4 py-3"
                style={{
                  background: "#0A1F44",
                  borderBottom: "1px solid #334155",
                }}
              >
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="text-white p-1 mr-3"
                  aria-label="Open menu"
                >
                  <svg
                    className="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 6h16M4 12h16M4 18h16"
                    />
                  </svg>
                </button>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/aminra-mark.png"
                  alt=""
                  className="h-7 w-7 mr-2 object-contain"
                />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="/aminra-wordmark-white.png"
                  alt="AMINRA"
                  className="h-4 object-contain"
                />
              </header>

              <main className="flex-1 p-5 md:p-8 lg:p-10 flex flex-col lg:min-h-0 lg:overflow-y-auto">
                <div className="w-full max-w-6xl mx-auto flex flex-col flex-1 lg:min-h-0">
                  {children}
                </div>
              </main>
            </div>
          </div>
        </FeatureFlagBootstrap>
      </AdminAuthProvider>
    </UserAuthProvider>
  );
}
