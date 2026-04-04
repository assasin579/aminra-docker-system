'use client';

import { useState } from 'react';
import Sidebar from './Sidebar';
import { AdminAuthProvider } from './AdminAuthContext';

export default function LayoutShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <AdminAuthProvider>
    <div className="flex min-h-screen lg:h-screen lg:overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 transition-transform duration-300 md:relative md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col lg:min-h-0 lg:overflow-hidden">
        {/* Mobile header */}
        <header
          className="md:hidden flex items-center px-4 py-3"
          style={{ background: '#111725', borderBottom: '1px solid #1e3a5f' }}
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
          <div className="h-7 w-7 rounded-full bg-green-600 flex items-center justify-center mr-2">
            <span className="text-white font-bold text-sm">M</span>
          </div>
          <span className="text-white font-bold">Mukjizat Saigoncert</span>
        </header>

        <main className="flex-1 p-4 md:p-6 flex flex-col lg:min-h-0 lg:overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
    </AdminAuthProvider>
  );
}
