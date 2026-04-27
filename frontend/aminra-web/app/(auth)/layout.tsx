import type { ReactNode } from 'react';

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className="flex-1 lg:min-h-0 grid place-items-center p-6 md:p-10"
      style={{ background: 'linear-gradient(135deg, #E8F5EF 0%, #F7F1E6 100%)' }}
    >
      {children}
    </div>
  );
}
