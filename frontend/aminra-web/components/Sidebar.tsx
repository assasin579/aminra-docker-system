"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { useState, useEffect, useRef } from "react";
import { useAdminAuth } from "./AdminAuthContext";
import { useUserAuth } from "./UserAuthContext";
import NotificationBell from "./NotificationBell";

export default function Sidebar({ onClose }: { onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const [clientReady, setClientReady] = useState(false);
  const { isAdmin, login: adminLogin, logout: logoutAdmin } = useAdminAuth();
  const { user, isAuthenticated, logout: logoutUser, token } = useUserAuth();
  const [avatarOpen, setAvatarOpen] = useState(false);
  const avatarRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setClientReady(true);
  }, []);

  // Close avatar dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (avatarRef.current && !avatarRef.current.contains(e.target as Node))
        setAvatarOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);


  const isAdminRoute = pathname.startsWith("/admin");
  const shouldShowAdminNavigation = isAdminRoute && isAdmin;

  const dashboardHref = shouldShowAdminNavigation
    ? null
    : user?.role === "business"
      ? "/dashboard/business"
      : user?.role === "provider"
        ? "/dashboard/provider"
        : null;

  // Company initial for avatar
  const companyInitial = user?.company_name?.charAt(0)?.toUpperCase() || "A";
  const logoUrl = user?.tenant_id
    ? `/api/auth/company-logo/${user.tenant_id}`
    : null;

  const adminNavItems = [
    { label: "Admin Panel", href: "/admin" },
    { label: "Analytics", href: "/admin/analytics" },
    { label: "Audit logs", href: "/admin/audit-logs" },
    { label: "Overdue queue", href: "/admin/overdue-submissions" },
    { label: "Standards", href: "/admin/standards" },
    { label: "Industries ↔ Standards", href: "/admin/industries" },
  ].map((item) => ({
    ...item,
    icon: (
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth="2"
          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
      </svg>
    ),
  }));

  const navItems = shouldShowAdminNavigation
    ? adminNavItems
    : [
    ...(!shouldShowAdminNavigation && dashboardHref
      ? [
          {
            label: "Dashboard",
            href: dashboardHref,
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
                />
              </svg>
            ),
          },
        ]
      : []),
    {
      label: t("navbar.home"),
      href: "/chat",
      icon: (
        <svg
          className="w-5 h-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      ),
    },
    ...(!shouldShowAdminNavigation && user?.role === "business"
      ? [
          {
            label: "Tài liệu",
            href: "/documents",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            ),
          },
          {
            label: "Hồ sơ đã gửi",
            href: "/submissions",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(!shouldShowAdminNavigation && user?.role === "business" && user?.is_owner
      ? [
          {
            label: "Thành viên",
            href: "/members",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(!shouldShowAdminNavigation && user?.role === "business"
      ? [
          {
            label: "Nguyên vật liệu",
            href: "/supply-chain/materials",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
            ),
          },
          {
            label: "Quy trình",
            href: "/supply-chain/process",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7"
                />
              </svg>
            ),
          },
          {
            label: "Lô hàng",
            href: "/supply-chain/batches",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(!shouldShowAdminNavigation && user?.role === "provider" && user?.is_owner
      ? [
          {
            label: "Doanh nghiệp",
            href: "/portfolio",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                />
              </svg>
            ),
          },
          {
            label: "Chứng nhận",
            href: "/certificates",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
            ),
          },
          {
            label: "Quản lý Auditor",
            href: "/auditors",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(!shouldShowAdminNavigation && user?.role === "provider"
      ? [
          {
            label: "Hồ sơ nhận",
            href: "/submissions",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(!shouldShowAdminNavigation && user?.role === "provider"
      ? [
          {
            label: "Kiểm định",
            href: "/audits",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
                />
              </svg>
            ),
          },
        ]
      : []),
    ...(shouldShowAdminNavigation
      ? []
      : isAdmin
        ? [
          {
            label: "Admin Panel",
            href: "/admin",
            icon: (
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            ),
          },
        ]
        : []),
  ];

  return (
    <aside
      className="w-64 min-h-screen flex flex-col overflow-hidden"
      style={{ background: "#0A1F44", borderRight: "1px solid #334155" }}
    >
      {/* ── Top: AMINRA brand (luôn hiện, nền trắng để nổi bật) ── */}
      <div
        className="px-3 py-4"
        style={{ background: "#FFFFFF", borderBottom: "1px solid #E2E8F0" }}
      >
        <div className="flex items-center gap-3 px-2">
          <div
            className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
            style={{ background: "#FFFFFF" }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/aminra-mark.png"
              alt=""
              className="w-9 h-9 object-contain"
            />
          </div>
          <div className="flex flex-col gap-0.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/aminra-wordmark-navy.png"
              alt="AMINRA"
              className="h-5 object-contain self-start"
            />
          </div>
        </div>
      </div>

      {!shouldShowAdminNavigation && isAuthenticated && user && (
        <div
          className="px-3 py-3"
          style={{ borderBottom: "1px solid #334155" }}
        >
          <div ref={avatarRef} className="relative">
            <button
              onClick={() => setAvatarOpen(!avatarOpen)}
              className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg transition-all hover:bg-white/5"
              style={{ border: "1px solid transparent" }}
            >
              <div
                className="w-9 h-9 rounded-full grid place-items-center flex-shrink-0 overflow-hidden"
                style={{
                  background: "#0A1F44",
                  boxShadow: "0 0 0 2px #334155",
                }}
              >
                {logoUrl ? (
                  <img
                    src={logoUrl}
                    alt=""
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : null}
                <span className="text-white font-bold text-xs">
                  {companyInitial}
                </span>
              </div>
              <div className="flex-1 min-w-0 text-left overflow-hidden">
                <p className="text-sm font-semibold text-white truncate">
                  {user.company_name}
                </p>
                <p className="text-xs truncate" style={{ color: "#94A3B8" }}>
                  {user.email}
                </p>
              </div>
              <svg
                className={`w-3.5 h-3.5 flex-shrink-0 text-slate-400 transition-transform ${avatarOpen ? "rotate-180" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {avatarOpen && (
              <div
                className="absolute left-0 right-0 top-full mt-1 rounded-xl overflow-hidden shadow-xl z-50 animate-modal-content"
                style={{ background: "#263548", border: "1px solid #334155" }}
              >
                <div
                  className="px-4 py-2"
                  style={{ borderBottom: "1px solid #334155" }}
                >
                  <span
                    className="text-xs font-medium px-2 py-0.5 rounded"
                    style={{
                      background: "rgba(10,31,68,0.15)",
                      color: "#102A5C",
                    }}
                  >
                    {user.role === "business"
                      ? user.is_owner
                        ? "Chủ tài khoản"
                        : "Thành viên"
                      : "Tổ chức"}
                  </span>
                </div>
                <div className="py-1">
                  <Link
                    href="/settings/company"
                    onClick={() => {
                      setAvatarOpen(false);
                      onClose?.();
                    }}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      style={{ color: "#94A3B8" }}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                      />
                    </svg>
                    Thông tin doanh nghiệp
                  </Link>
                  <Link
                    href="/settings"
                    onClick={() => {
                      setAvatarOpen(false);
                      onClose?.();
                    }}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm text-slate-300 hover:bg-white/5 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      style={{ color: "#94A3B8" }}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                      />
                    </svg>
                    Cài đặt tài khoản
                  </Link>
                </div>
                <div style={{ borderTop: "1px solid #334155" }}>
                  <button
                    onClick={() => {
                      logoutUser();
                      router.push("/landing");
                      setAvatarOpen(false);
                      onClose?.();
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                  >
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                      />
                    </svg>
                    Đăng xuất
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Admin logged in or active admin route ── */}
      {shouldShowAdminNavigation && (
        <div
          className="px-3 py-3"
          style={{ borderBottom: "1px solid #334155" }}
        >
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg"
            style={{
              background: "rgba(10,31,68,0.08)",
              border: "1px solid rgba(10,31,68,0.2)",
            }}
          >
            <span style={{ color: "#102A5C", fontSize: 10 }}>●</span>
            <span className="text-xs font-medium" style={{ color: "#102A5C" }}>
              AMINRA Platform Admin
            </span>
          </div>
        </div>
      )}

      {/* ── Navigation ── */}
      <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map((item, i) => {
          const [itemPath] = item.href.split("?");
          const active = shouldShowAdminNavigation
            ? pathname === itemPath
            : pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link animate-nav-item grid items-center px-3 py-2.5 rounded-lg ${
                active
                  ? "is-active bg-[#0A1F44] text-white shadow-md"
                  : "text-slate-300 hover:bg-white/5 hover:text-white"
              }`}
              style={{
                gridTemplateColumns: "1.25rem 1fr",
                gap: "0.625rem",
                animationDelay: `${i * 0.04}s`,
              }}
              onClick={onClose}
            >
              <span className="nav-active-bar" aria-hidden="true" />
              <div
                className={`transition-transform duration-200 ${active ? "text-white scale-110" : "text-[#C9A24A]"}`}
              >
                {item.icon}
              </div>
              <span className="font-medium text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* ── Notifications ── */}
      {!shouldShowAdminNavigation && isAuthenticated && (
        <div className="px-3 py-2" style={{ borderTop: "1px solid #334155" }}>
          <NotificationBell token={token || ""} />
        </div>
      )}

      {/* ── Login / Logout (when not logged in as user) ── */}
      {(!isAuthenticated || shouldShowAdminNavigation) && (
        <div
          className="px-3 py-3 space-y-1"
          style={{ borderTop: "1px solid #334155" }}
        >
          {isAdmin ? (
            <button
              onClick={() => {
                logoutAdmin();
                onClose?.();
              }}
              className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-slate-300 hover:bg-red-500/10 hover:text-red-400 transition-colors"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                />
              </svg>
              Đăng xuất Admin
            </button>
          ) : (
            <>
              <Link
                href="/business/login"
                onClick={onClose}
                className="flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-slate-300 hover:bg-[#0A1F44]/20 hover:text-white transition-colors"
              >
                <svg
                  className="w-5 h-5"
                  style={{ color: "#102A5C" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
                  />
                </svg>
                Đăng nhập Doanh nghiệp
              </Link>
              <Link
                href="/provider/login"
                onClick={onClose}
                className="flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-slate-300 hover:bg-[#0A1F44]/20 hover:text-white transition-colors"
              >
                <svg
                  className="w-5 h-5"
                  style={{ color: "#94A3B8" }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                  />
                </svg>
                Đăng nhập Tổ chức
              </Link>
              <button
                onClick={() => void adminLogin("/admin")}
                className="w-full flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium text-slate-300 hover:bg-[#0A1F44]/20 hover:text-white transition-colors"
              >
                <svg
                  className="w-5 h-5 text-[#C9A24A]"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                  />
                </svg>
                Đăng nhập Admin
              </button>
            </>
          )}
        </div>
      )}


      {/* ── Footer ── */}
      <div className="px-3 py-2" style={{ borderTop: "1px solid #334155" }}>
        <p
          className="text-xs text-center"
          style={{ color: "#94A3B8" }}
          suppressHydrationWarning
        >
          © {new Date().getFullYear()} AMINRA
        </p>
      </div>

    </aside>
  );
}
