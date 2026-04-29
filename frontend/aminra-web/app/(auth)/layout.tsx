import type { ReactNode } from 'react';

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className="min-h-screen w-full flex items-center justify-center px-4 py-8 sm:px-6 sm:py-10"
      style={{ background: 'linear-gradient(135deg, #DCE3F0 0%, #F5F1E8 100%)' }}
    >
      {children}
    </div>
  );
}
