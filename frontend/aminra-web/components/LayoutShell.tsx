'use client';

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import Sidebar from './Sidebar';
import { AdminAuthProvider } from './AdminAuthContext';
import { UserAuthProvider } from './UserAuthContext';

const FULL_SCREEN_ROUTES = ['/landing'];
const FULL_SCREEN_PREFIXES = ['/supplier-portal', '/invite', '/trace'];

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  const isFullScreen = FULL_SCREEN_ROUTES.includes(pathname) || FULL_SCREEN_PREFIXES.some(p => pathname.startsWith(p));

  // Landing page — no sidebar, no padding, full screen
  if (isFullScreen) {
    return (
      <UserAuthProvider>
      <AdminAuthProvider>
        <div className="min-h-screen">{children}</div>
      </AdminAuthProvider>
      </UserAuthProvider>
    );
  }

  return (
    <UserAuthProvider>
    <AdminAuthProvider>
    <div className="flex min-h-screen lg:h-screen lg:overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden animate-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar — fixed width, no shrink */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 flex-shrink-0 transition-transform duration-300 md:relative md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main content — takes remaining space */}
      <div className="flex-1 min-w-0 flex flex-col lg:min-h-0 lg:overflow-hidden">
        {/* Mobile header */}
        <header
          className="md:hidden flex items-center px-4 py-3"
          style={{ background: '#1E293B', borderBottom: '1px solid #334155' }}
        >
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-white p-1 mr-3"
            aria-label="Open menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="h-7 w-7 rounded-full bg-emerald-700 flex items-center justify-center mr-2">
            <span className="text-white font-bold text-sm">A</span>
          </div>
          <span className="text-white font-bold">Aminra</span>
        </header>

        <main className="flex-1 p-5 md:p-8 lg:p-10 flex flex-col lg:min-h-0 lg:overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
    </AdminAuthProvider>
    </UserAuthProvider>
  );
}
